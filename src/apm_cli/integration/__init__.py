"""APM package integration utilities."""

from .agent_integrator import AgentIntegrator
from .base_integrator import BaseIntegrator, IntegrationResult
from .hook_integrator import HookIntegrator
from .instruction_integrator import InstructionIntegrator
from .mcp_integrator import MCPIntegrator
from .prompt_integrator import PromptIntegrator
from .skill_integrator import (
    SkillIntegrator,
    copy_skill_to_target,
    get_effective_type,
    normalize_skill_name,
    should_compile_instructions,
    should_install_skill,
    to_hyphen_case,
    validate_skill_name,
)
from .skill_transformer import SkillTransformer
from .targets import (
    KNOWN_TARGETS,
    PrimitiveMapping,
    TargetProfile,
    active_targets,
    get_integration_prefixes,
)

__all__ = [
    'BaseIntegrator',
    'IntegrationResult',
    'PromptIntegrator',
    'AgentIntegrator',
    'HookIntegrator',
    'InstructionIntegrator',
    'SkillIntegrator',
    'SkillTransformer',
    'MCPIntegrator',
    'TargetProfile',
    'PrimitiveMapping',
    'KNOWN_TARGETS',
    'get_integration_prefixes',
    'active_targets',
    'validate_skill_name',
    'normalize_skill_name',
    'to_hyphen_case',
    'copy_skill_to_target',
    'should_install_skill',
    'should_compile_instructions',
    'get_effective_type',
]
