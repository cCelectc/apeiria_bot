"""Canonical production composition for selected AI domain services."""

from __future__ import annotations

from apeiria.ai.knowledge.service import KnowledgeRetrievalService
from apeiria.ai.memory.service import AIMemoryService
from apeiria.ai.persona.service import AIPersonaService
from apeiria.ai.profile.service import AIProfileService
from apeiria.ai.relationship.service import AIRelationshipService
from apeiria.ai.retention import AIRetentionService
from apeiria.ai.retrieval.service import RetrievalCandidateService
from apeiria.ai.skills.service import AISkillService
from apeiria.ai.tools.policy import AIToolPolicyBindingService
from apeiria.ai.tools.service import AIToolService
from apeiria.app.ai.model_wiring import AIModelWiring


class AIWiring:
    """Lazy app-layer composition root for selected AI domain services."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        tool_policy_binding_service: AIToolPolicyBindingService | None = None,
        tool_service: AIToolService | None = None,
        skill_service: AISkillService | None = None,
        memory_service: AIMemoryService | None = None,
        persona_service: AIPersonaService | None = None,
        profile_service: AIProfileService | None = None,
        relationship_service: AIRelationshipService | None = None,
        knowledge_service: KnowledgeRetrievalService | None = None,
        retrieval_service: RetrievalCandidateService | None = None,
        retention_service: AIRetentionService | None = None,
        model: AIModelWiring | None = None,
    ) -> None:
        self._tool_policy_binding_service = tool_policy_binding_service
        self._tool_service = tool_service
        self._skill_service = skill_service
        self._memory_service = memory_service
        self._persona_service = persona_service
        self._profile_service = profile_service
        self._relationship_service = relationship_service
        self._knowledge_service = knowledge_service
        self._retrieval_service = retrieval_service
        self._retention_service = retention_service
        self._model = model

    @property
    def model(self) -> AIModelWiring:
        if self._model is None:
            self._model = AIModelWiring()
        return self._model

    @property
    def tool_policy_binding_service(self) -> AIToolPolicyBindingService:
        if self._tool_policy_binding_service is None:
            self._tool_policy_binding_service = AIToolPolicyBindingService()
        return self._tool_policy_binding_service

    @property
    def tool_service(self) -> AIToolService:
        if self._tool_service is None:
            self._tool_service = AIToolService()
        return self._tool_service

    @property
    def skill_service(self) -> AISkillService:
        if self._skill_service is None:
            self._skill_service = AISkillService()
        return self._skill_service

    @property
    def retrieval_service(self) -> RetrievalCandidateService:
        if self._retrieval_service is None:
            self._retrieval_service = RetrievalCandidateService(
                capability_selection_service=self.model.capability_selection_service,
                model_invoker=self.model.invoker,
                source_service=self.model.source_service,
            )
        return self._retrieval_service

    @property
    def memory_service(self) -> AIMemoryService:
        if self._memory_service is None:
            self._memory_service = AIMemoryService(
                retrieval=self.retrieval_service,
            )
        return self._memory_service

    @property
    def persona_service(self) -> AIPersonaService:
        if self._persona_service is None:
            self._persona_service = AIPersonaService()
        return self._persona_service

    @property
    def profile_service(self) -> AIProfileService:
        if self._profile_service is None:
            self._profile_service = AIProfileService()
        return self._profile_service

    @property
    def relationship_service(self) -> AIRelationshipService:
        if self._relationship_service is None:
            self._relationship_service = AIRelationshipService()
        return self._relationship_service

    @property
    def knowledge_service(self) -> KnowledgeRetrievalService:
        if self._knowledge_service is None:
            self._knowledge_service = KnowledgeRetrievalService(
                retrieval=self.retrieval_service,
            )
        return self._knowledge_service

    @property
    def retention_service(self) -> AIRetentionService:
        if self._retention_service is None:
            self._retention_service = AIRetentionService()
        return self._retention_service


ai_wiring = AIWiring()

__all__ = ["AIWiring", "ai_wiring"]
