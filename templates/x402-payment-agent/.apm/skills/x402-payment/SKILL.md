# x402 Payment Negotiation

Handle the HTTP 402 → pay → retry cycle for premium API access.

## When to Use

Use this skill when:
- An API returns HTTP 402 (Payment Required)
- A user asks to fetch data from a paid endpoint
- You need to check payment requirements before accessing a resource

## Steps

1. **Initial request** — Make the HTTP GET/POST to the target URL
2. **Parse 402 response** — Extract: `amount`, `payTo`, `asset`, `network` from the JSON body
3. **Check policy** — Apply spending-policy instructions (per-tx cap, daily limit, allowlist)
4. **Sign payment** — Use the agentpay-mcp `x402_pay` tool to sign a payment proof
5. **Retry with proof** — Resend the original request with the `X-PAYMENT` header containing the signed proof
6. **Report result** — Return the API response to the user, or report the denial reason

## Error Handling

- If the 402 response body is not valid JSON: report "unsupported payment format"
- If no amount is specified: report "missing payment requirements"
- If the retry still fails after payment: report the HTTP status and response
- Never retry more than once per payment
