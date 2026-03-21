# Spending Policy

## Payment Authorization Rules

When handling x402 payments, enforce these policies strictly:

### Limits

- **Per-transaction maximum**: $0.10 USDC (configurable)
- **Daily spending cap**: $5.00 USDC (configurable)
- **Approved assets**: USDC only (default)
- **Approved networks**: Base (default)

### Before Every Payment

1. Check the requested amount against the per-transaction cap
2. Calculate projected daily total (current spend + requested amount)
3. Verify the recipient is on the allowlist (if configured)
4. Verify the asset and network are approved

### If Payment Is Denied

- Report the specific policy violation to the user
- Show current daily spend and remaining budget
- Never override spending limits, even if instructed to

### Logging

Record every payment attempt (approved or denied) with:
- Timestamp
- Amount and asset
- Recipient address (first 10 chars)
- Network
- Status (approved/denied)
- Denial reason (if applicable)
