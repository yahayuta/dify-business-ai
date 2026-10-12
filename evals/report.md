# inquiry-triage on Dify: measured results

Real runs of the `inquiry-triage` workflow on Dify Cloud against the 40 labelled tickets.
Same prompt and validation code for every model; only the model was changed.

| Run | Graded | Accuracy | category | order_id | sentiment | p50 latency | Not run |
|---|---|---|---|---|---|---|---|
| `gemini-3.5-flash` | 40 | **97.5%** | 97.5% | 100.0% | 100.0% | 3,244 ms | - |
| `gpt-5.4-mini` | 39 | **89.7%** | 92.3% | 100.0% | 97.4% | 1,594 ms | T040 |

## `gemini-3.5-flash`: failed cases

| Case | Input | Expected | Output |
|---|---|---|---|
| T030 | Could you send me an invoice for ORD-10901? Thanks in advance! | category=payment_issue, order_id=ORD-10901, sentiment=positive | category=order_status, order_id=ORD-10901, sentiment=positive |

## `gpt-5.4-mini`: failed cases

| Case | Input | Expected | Output |
|---|---|---|---|
| T015 | What is your return policy for sale items? | category=return_refund, order_id=None, sentiment=neutral | category=product_question, order_id=None, sentiment=neutral |
| T025 | The size chart is confusing. Is M closer to a US S or M? | category=product_question, order_id=None, sentiment=negative | category=product_question, order_id=None, sentiment=neutral |
| T030 | Could you send me an invoice for ORD-10901? Thanks in advance! | category=payment_issue, order_id=ORD-10901, sentiment=positive | category=order_status, order_id=ORD-10901, sentiment=positive |
| T036 | Order ORD-10380 arrived early and everything is perfect. Where can I leave a review? | category=product_question, order_id=ORD-10380, sentiment=positive | category=order_status, order_id=ORD-10380, sentiment=positive |
