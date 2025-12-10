# utils/cost_calculator.py

from constants.rates import INPUT_COST_GPT_4O_MINI, OUPUT_COST_GPT_4O_MINI
import requests
def calculate_cost(input_tokens: int, output_tokens: int):
    """
    Calculates cost separately for input & output tokens based on GPT-4o-mini pricing.
    """
    rate=88.0
    try:
        response = requests.get("https://api.frankfurter.dev/v1/latest?base=USD&symbols=INR")
        data = response.json()
        rate = data["rates"]["INR"]
    except Exception as e:
        print("Error fetching USD to INR conversion rate:", e)

    input_cost = (input_tokens / 1_000_000) * INPUT_COST_GPT_4O_MINI*rate
    output_cost = (output_tokens / 1_000_000) * OUPUT_COST_GPT_4O_MINI*rate
    total_cost = input_cost + output_cost

          # fallback (optional)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost
    }
