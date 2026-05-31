import random
from typing import Optional
from loguru import logger
from prompt_ops.database.connection import get_session
from prompt_ops.database.models import PromptVersion, OptimizationRun
from prompt_ops.config import settings

class PromptManager:
    def create_version(self, prompt_id: str, template: str, name: str, traffic_weight: float = 1.0) -> PromptVersion:
        with get_session() as session:
            existing = session.query(PromptVersion).filter_by(prompt_id=prompt_id, version_name=name).first()
            if existing:
                existing.template = template
                existing.traffic_weight = traffic_weight
                existing.is_active = True
                session.commit()
                session.refresh(existing)
                return existing
            
            new_version = PromptVersion(
                prompt_id=prompt_id,
                version_name=name,
                template=template,
                traffic_weight=traffic_weight
            )
            session.add(new_version)
            session.commit()
            session.refresh(new_version)
            return new_version

    def select_version(self, prompt_id: str) -> Optional[PromptVersion]:
        with get_session() as session:
            versions = session.query(PromptVersion).filter_by(prompt_id=prompt_id, is_active=True).all()
            if not versions:
                return None
            
            weights = [v.traffic_weight for v in versions]
            if sum(weights) == 0:
                weights = [1.0 for _ in versions]
            
            return random.choices(versions, weights=weights, k=1)[0]

    def update_metrics(self, version_id: int, quality_score: float) -> None:
        if quality_score is None:
            return
            
        with get_session() as session:
            version = session.query(PromptVersion).filter_by(id=version_id).first()
            if not version:
                return
            
            old_total_score = version.avg_quality_score * version.request_count
            version.request_count += 1
            version.avg_quality_score = (old_total_score + quality_score) / version.request_count
            session.commit()
            
            self.maybe_promote(version.prompt_id)

    def maybe_promote(self, prompt_id: str) -> None:
        with get_session() as session:
            versions = session.query(PromptVersion).filter_by(prompt_id=prompt_id, is_active=True).all()
            if not versions or len(versions) < 2:
                return
            
            # Auto-retire: deactivate versions with poor quality after enough samples
            for v in versions:
                if v.request_count >= 20 and v.avg_quality_score < settings.auto_retire_threshold:
                    v.is_active = False
                    v.traffic_weight = 0.0
                    logger.info(f"Auto-retiring version '{v.version_name}' for prompt '{prompt_id}' (quality={v.avg_quality_score:.3f} < {settings.auto_retire_threshold})")
                    run = OptimizationRun(
                        prompt_id=prompt_id,
                        run_type="auto_retire",
                        from_version=v.version_name,
                        to_version=None,
                        quality_before=v.avg_quality_score,
                        quality_after=0.0,
                        notes=f"Auto-retired: quality {v.avg_quality_score:.3f} below threshold {settings.auto_retire_threshold}"
                    )
                    session.add(run)
            
            # Re-query active versions after retirement
            versions = session.query(PromptVersion).filter_by(prompt_id=prompt_id, is_active=True).all()
            if not versions or len(versions) < 2:
                session.commit()
                return
            
            # Auto-promote: find the best version
            eligible = [v for v in versions if v.request_count >= 20 and v.avg_quality_score >= settings.auto_promote_threshold]
            if not eligible:
                session.commit()
                return
                
            best = max(eligible, key=lambda v: v.avg_quality_score)
            
            # Check if strictly better than others
            others = [v for v in versions if v.id != best.id]
            best_other = max(others, key=lambda v: v.avg_quality_score).avg_quality_score if others else 0.0
            
            if best.avg_quality_score > best_other:
                logger.info(f"Auto-promoting version '{best.version_name}' for prompt '{prompt_id}' (quality={best.avg_quality_score:.3f})")
                
                # Log the promotion
                run = OptimizationRun(
                    prompt_id=prompt_id,
                    run_type="auto_promote",
                    from_version="mixed",
                    to_version=best.version_name,
                    quality_before=best_other,
                    quality_after=best.avg_quality_score,
                    notes=f"Auto-promoted '{best.version_name}' (quality={best.avg_quality_score:.3f}) over others (best_other={best_other:.3f})"
                )
                session.add(run)
                
                for v in versions:
                    if v.id == best.id:
                        v.traffic_weight = 1.0
                    else:
                        v.traffic_weight = 0.0
            session.commit()

prompt_manager = PromptManager()
