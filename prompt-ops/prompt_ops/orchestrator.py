import time
import inspect
import random
from prompt_ops.client import llm_client, LLMResponse
from prompt_ops.config import settings
from loguru import logger
from concurrent.futures import ThreadPoolExecutor
from prompt_ops.optimizer import prompt_manager
from prompt_ops.temperature import temperature_optimizer
from prompt_ops.telemetry import telemetry_tracker
from prompt_ops.evaluator import evaluator
from prompt_ops.router import route_with_cascade
from prompt_ops.database.connection import get_session
from prompt_ops.database.models import EvaluationResult as DbEvaluationResult

class Orchestrator:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=5)

    def execute_and_log(self, func, prompt_id: str, ab_testing: bool, enable_cost_routing: bool, *args, **kwargs):
        # Fallback return directly avoiding crashes
        def direct_fallback():
            return func(*args, **kwargs)

        try:
            # Analyze signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            prompt_str = bound_args.arguments.get("prompt")
            if not isinstance(prompt_str, str):
                for name, val in bound_args.arguments.items():
                    if isinstance(val, str):
                        prompt_str = val
                        break
            if not prompt_str:
                prompt_str = "Unknown prompt"

            # Versioning
            version_name = None
            if ab_testing:
                version = prompt_manager.select_version(prompt_id)
                if version:
                    version_name = version.version_name
                    prompt_str = version.template.replace("{input}", prompt_str)
                    
                    if "prompt" in bound_args.arguments:
                        bound_args.arguments["prompt"] = prompt_str

            # Check for best temperature
            best_temp = temperature_optimizer.get_best_temperature(prompt_id)
            if best_temp is not None:
                if "temperature" in bound_args.arguments or "temperature" in inspect.signature(func).parameters:
                    bound_args.arguments["temperature"] = best_temp
            
            # Start tracking
            requested_model = bound_args.arguments.get("model", "google/gemini-2.0-flash-001")
            used_model = requested_model

            start_time = time.monotonic()
            cost_saved_usd = 0.0

            # Execute
            if enable_cost_routing and "model" in bound_args.arguments:
                def model_caller(p_text, model=None, **kw):
                    bound_args.arguments["model"] = model
                    return func(*bound_args.args, **bound_args.kwargs)
                response, used_model = route_with_cascade(prompt_id, prompt_str, model_caller, requested_model)
            else:
                response = func(*bound_args.args, **bound_args.kwargs)

            latency_ms = (time.monotonic() - start_time) * 1000

            # Extract real telemetry data if the response is from our LLMClient
            tokens_in = 0
            tokens_out = 0
            cost = 0.0
            success = True
            error_msg = None
            
            if isinstance(response, LLMResponse):
                tokens_in = response.input_tokens
                tokens_out = response.output_tokens
                cost = response.cost_usd
                success = response.success
                error_msg = response.error

            # Async Eval + log
            log_id = telemetry_tracker.log_request(
                prompt_id=prompt_id,
                version=version_name,
                model=used_model,
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=cost,
                success=success,
                error=error_msg
            )
            
            # Update aggregated model metrics
            telemetry_tracker.update_model_metrics(
                model=used_model,
                latency_ms=latency_ms,
                quality=None,  # Will be updated by evaluator if it runs
                cost=cost,
                success=success
            )

            # Do not block main thread
            from prompt_ops.decorator import OptimizeResult # late import avoids circular
            result_obj = OptimizeResult(
                content=response,
                prompt_version=version_name,
                model_used=used_model,
                cost_saved_usd=cost_saved_usd,
                latency_ms=latency_ms
            )

            def background_eval():
                try:
                    if settings.auto_evaluate and success:
                        if random.random() <= settings.evaluation_sample_rate:
                            response_text = response.content if isinstance(response, LLMResponse) else str(response)
                            eval_res = evaluator.evaluate(prompt_str, response_text, prompt_id, version_name or "default")
                            if eval_res:
                                result_obj.quality_score = eval_res.composite
                                telemetry_tracker.update_quality(log_id, eval_res.composite)
                                
                                if version_name:
                                    with get_session() as session:
                                        from prompt_ops.database.models import PromptVersion
                                        version = session.query(PromptVersion).filter_by(prompt_id=prompt_id, version_name=version_name).first()
                                        if version:
                                            prompt_manager.update_metrics(version.id, eval_res.composite)
                                            
                                with get_session() as session:
                                    db_eval = DbEvaluationResult(
                                        telemetry_log_id=log_id,
                                        relevance=eval_res.relevance,
                                        accuracy=eval_res.accuracy,
                                        completeness=eval_res.completeness,
                                        format_compliance=eval_res.format_compliance,
                                        safety=eval_res.safety,
                                        composite=eval_res.composite,
                                        timestamp=eval_res.timestamp
                                    )
                                    session.add(db_eval)
                                    session.commit()

                except Exception as e:
                    logger.error(f"Error in background eval: {e}")

            self.executor.submit(background_eval)
            return result_obj
            
        except Exception as e:
            logger.error(f"Error in orchestrator: {e}")
            from prompt_ops.decorator import OptimizeResult
            try:
                base_ret = direct_fallback()
                return OptimizeResult(content=base_ret)
            except Exception as inner_e:
                raise inner_e

orchestrator = Orchestrator()
