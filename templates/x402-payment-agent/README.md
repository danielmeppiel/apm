# x402 Payment Agent Template

An APM template for AI agents that need to access paid APIs autonomously.

## What is x402?

The [x402 protocol](https://github.com/coinbase/x402) (by Coinbase) standardizes HTTP 402 (Payment Required) responses for machine-to-machine payments. When an API requires payment, it returns a 402 with payment requirements. The agent evaluates the cost, signs a USDC payment, and retries — all without human intervention.

## Quick Start

```bash
# Initialize a new project from this template
apm init --template x402-payment-agent

# Install dependencies (including agentpay-mcp server)
apm install
apm compile
```

## What's Included

| Primitive | Description |
|-----------|-------------|
| **Instructions** | Spending policy rules — per-tx caps, daily limits, recipient allowlists |
| **Skills** | x402 payment negotiation workflow (402 → evaluate → pay → retry) |
| **Prompts** | Test payment flow, check budget status |
| **MCP Server** | `agentpay-mcp` — 7 payment-domain tools |

## Spending Policy

The default policy is conservative:
- **$0.10** max per transaction
- **$5.00** daily cap
- **USDC on Base** only

Edit `.apm/instructions/spending-policy.instructions.md` to customize.

## Ecosystem

This payment pattern is implemented across multiple agent frameworks:
- [NVIDIA NeMo Agent Toolkit](https://github.com/NVIDIA/NeMo-Agent-Toolkit-Examples/pull/17) (merged)
- [Google ADK](https://github.com/google/adk-python/pull/4937) (submitted)
- [Microsoft AutoGen](https://github.com/microsoft/autogen/pull/7346) (submitted)

## Links

- [x402 Protocol](https://github.com/coinbase/x402)
- [agentpay-mcp](https://github.com/up2itnow0822/agentpay-mcp)
- [agentwallet-sdk](https://www.npmjs.com/package/agentwallet-sdk)
