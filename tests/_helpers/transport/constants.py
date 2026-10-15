"""
Description:
Stałe podmienionego transportu HTTP.
"""

# Odpowiedź na żądanie, którego nie dopasowała żadna trasa. Przyzwalająca zamiast 404, żeby test
# wymieniał tylko wywołania, które go obchodzą; test, któremu zależy na chybieniu, sprawdza to,
# co zostało przechwycone.
DEFAULT_RESPONSE_BODY = {
    "result": {},
    "status": "ok",
}
