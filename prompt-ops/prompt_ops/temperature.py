import json
from dataclasses import dataclass
from statistics import mean, stdev
from prompt_ops.database.connection import get_session
from prompt_ops.database.models import TemperatureExperiment
from prompt_ops.evaluator import evaluator

@dataclass
class TemperatureResult:
    prompt_id: str
    best_temperature: float
    best_composite_score: float
    all_results: list[dict]

class TemperatureOptimizer:
    def get_best_temperature(self, prompt_id: str) -> float | None:
        with get_session() as session:
            exp = session.query(TemperatureExperiment).filter_by(prompt_id=prompt_id).first()
            if exp:
                return exp.best_temperature
        return None

    def run_experiment(
        self,
        prompt_id: str,
        prompt_text: str,
        call_llm_func,
        temp_min: float = 0.0,
        temp_max: float = 1.5,
        temp_step: float = 0.3,
        trials_per_step: int = 3,
    ) -> TemperatureResult:
        all_results = []
        best_temp = 0.0
        max_composite = -1.0
        
        temps_to_try = []
        t = temp_min
        while t <= temp_max:
            temps_to_try.append(t)
            t += temp_step
            
        for temp in temps_to_try:
            scores = []
            for _ in range(trials_per_step):
                response = call_llm_func(prompt_text, temperature=temp)
                res = evaluator.evaluate(prompt_text, response, prompt_id, "experiment")
                if res and res.composite is not None:
                    scores.append(res.composite)
                else:
                    scores.append(0.0)
            
            avg_quality = mean(scores) if scores else 0.0
            consistency = 1 - stdev(scores) if len(scores) > 1 else 1.0
            composite = avg_quality * (0.7 + 0.3 * consistency)
            
            all_results.append({
                "temp": temp,
                "avg_quality": avg_quality,
                "consistency": consistency,
                "composite": composite
            })
            
            if composite > max_composite:
                max_composite = composite
                best_temp = temp

        result = TemperatureResult(
            prompt_id=prompt_id,
            best_temperature=best_temp,
            best_composite_score=max_composite,
            all_results=all_results
        )

        with get_session() as session:
            existing = session.query(TemperatureExperiment).filter_by(prompt_id=prompt_id).first()
            if existing:
                existing.best_temperature = best_temp
                existing.best_composite_score = max_composite
                existing.results_json = json.dumps(all_results)
            else:
                new_exp = TemperatureExperiment(
                    prompt_id=prompt_id,
                    best_temperature=best_temp,
                    best_composite_score=max_composite,
                    results_json=json.dumps(all_results)
                )
                session.add(new_exp)
            session.commit()

        return result

temperature_optimizer = TemperatureOptimizer()
