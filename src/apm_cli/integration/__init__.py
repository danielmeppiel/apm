"""APM package integration utilities."""

from .base_integrator import BaseIntegrator, IntegrationResult
from .prompt_integrator import PromptIntegrator
from .agent_integrator import AgentIntegrator
from .hook_integrator import HookIntegrator
from .skill_integrator import (
    SkillIntegrator,
    validate_skill_name,
    normalize_skill_name,
    to_hyphen_case,
    copy_skill_to_target,
    should_install_skill,
    should_compile_instructions,
    get_effective_type,
)
from .skill_transformer import SkillTransformer

__all__ = [
    'BaseIntegrator',
    'IntegrationResult',
    'PromptIntegrator',
    'AgentIntegrator',
    'HookIntegrator',
    'SkillIntegrator',
    'SkillTransformer',
    'validate_skill_name',
    'normalize_skill_name',
    'to_hyphen_case',
    'copy_skill_to_target',
    'should_install_skill',
    'should_compile_instructions',
    'get_effective_type',
]
