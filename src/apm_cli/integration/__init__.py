"""APM package integration utilities."""

from .base_integrator import BaseIntegrator, IntegrationResult
from .prompt_integrator import PromptIntegrator
from .agent_integrator import AgentIntegrator
from .hook_integrator import HookIntegrator
from .instruction_integrator import InstructionIntegrator
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
from .mcp_integrator import MCPIntegrator
from .targets import (
    TargetProfile,
    PrimitiveMapping,
    KNOWN_TARGETS,
    INTEGRATION_DISPATCH,
    get_integration_prefixes,
    active_targets,
    integrate_package_for_targets,
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
    'INTEGRATION_DISPATCH',
    'get_integration_prefixes',
    'active_targets',
    'integrate_package_for_targets',
    'validate_skill_name',
    'normalize_skill_name',
    'to_hyphen_case',
    'copy_skill_to_target',
    'should_install_skill',
    'should_compile_instructions',
    'get_effective_type',
]
