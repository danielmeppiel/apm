---
name: x402-payment-agent
description: Handle HTTP 402 (Payment Required) responses using the x402 protocol — autonomous API payment with spending policy enforcement.
---

# x402 Payment Agent

Enables AI agents to autonomously pay for premium API access using the [x402 protocol](https://github.com/coinbase/x402).

## What This Package Does

When an agent encounters an HTTP 402 response, this package provides the instructions, skills, and MCP server integration to:

1. Parse x402 payment requirements from the 402 response
2. Evaluate the payment against configurable spending policies
3. Sign and submit USDC payments on Base (or other supported networks)
4. Retry the original request with the payment proof

## Getting Started

```bash
apm install up2itnow0822/x402-payment-agent
apm compile
```

## Available Primitives

- **Instructions**: Spending policy rules and payment safety guidelines in `.apm/instructions/`
- **Skills**: x402 payment negotiation workflow in `.apm/skills/x402-payment/`
- **Prompts**: Test payment flow against a mock server in `.apm/prompts/`
- **MCP Server**: `agentpay-mcp` — 7 payment-domain tools (balance, transfer, x402, bridge, spend limits)

## Included Workflows

- `test-payment.prompt.md` — Test the x402 payment flow against a mock 402 endpoint
- `check-budget.prompt.md` — Review current spending totals and remaining budget

## Related

- [x402 Protocol (Coinbase)](https://github.com/coinbase/x402)
- [agentpay-mcp](https://github.com/up2itnow0822/agentpay-mcp) — MCP server for agent payments
- [agentwallet-sdk](https://www.npmjs.com/package/agentwallet-sdk) — Non-custodial wallet SDK
