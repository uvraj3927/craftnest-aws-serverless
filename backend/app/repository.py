import boto3
from boto3.dynamodb.conditions import Key

from .config import ORDERS_TABLE, SNS_TOPIC_ARN, USERS_TABLE

_dynamodb = boto3.resource("dynamodb")
_sns = boto3.client("sns")
_users = _dynamodb.Table(USERS_TABLE)
_orders = _dynamodb.Table(ORDERS_TABLE)


def get_user(email: str):
    result = _users.get_item(Key={"email": email}, ConsistentRead=True)
    return result.get("Item")


def create_user(user: dict):
    _users.put_item(
        Item=user,
        ConditionExpression="attribute_not_exists(email)",
    )


def create_order(order: dict):
    _orders.put_item(
        Item=order,
        ConditionExpression="attribute_not_exists(order_id)",
    )


def list_user_orders(email: str):
    # Requires a GSI on OrdersTable with partition key user_email.
    result = _orders.query(
        IndexName="user_email-index",
        KeyConditionExpression=Key("user_email").eq(email),
        ScanIndexForward=False,
    )
    items = result.get("Items", [])
    while "LastEvaluatedKey" in result:
        result = _orders.query(
            IndexName="user_email-index",
            KeyConditionExpression=Key("user_email").eq(email),
            ScanIndexForward=False,
            ExclusiveStartKey=result["LastEvaluatedKey"],
        )
        items.extend(result.get("Items", []))
    return items


def publish_order_confirmation(order: dict):
    message = {
        "event": "ORDER_CONFIRMATION",
        "order_id": order["order_id"],
        "user_email": order["user_email"],
        "total_amount": order["total_amount"],
        "status": order["status"],
        "created_at": order["created_at"],
    }
    return _sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"CraftNest order confirmation: {order['order_id']}",
        Message=__import__("json").dumps(message, default=str),
    )
