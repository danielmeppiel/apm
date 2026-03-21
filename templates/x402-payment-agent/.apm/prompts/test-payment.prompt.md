# Test x402 Payment Flow

Test the x402 payment negotiation cycle against a mock endpoint.

## Steps

1. Start the mock x402 server (if available locally):
   ```bash
   python mock_server.py
   ```

2. Fetch data from the paid endpoint:
   - URL: `http://localhost:8402/v1/market-data`
   - Expected: HTTP 402 with payment requirements

3. Process the payment:
   - Amount should be 0.05 USDC
   - Recipient: mock address
   - Use agentpay-mcp to sign the payment

4. Retry with payment proof:
   - Expected: HTTP 200 with market data response

5. Report:
   - Payment amount and recipient
   - Response data received
   - Updated daily spending total
