import os

USERS_TABLE = os.environ["USERS_TABLE"]
ORDERS_TABLE = os.environ["ORDERS_TABLE"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

# Required for signed session tokens. Store this in AWS Secrets Manager or
# Parameter Store (not in source control). Use a long random value.
SESSION_SECRET = os.environ["SESSION_SECRET"].encode("utf-8")

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", "310000"))
CORS_ALLOW_ORIGIN = os.getenv("CORS_ALLOW_ORIGIN", "*")
