# CraftNest -- Serverless Handmade Crafts Store

A beginner-friendly AWS project that demonstrates how to host a small
e-commerce website using serverless services.

CraftNest is a handmade crafts storefront. Customers can browse
products, register or log in, place orders, and view their order
history. The learning goal is not only building the website, but
understanding how AWS services work together and how to troubleshoot
them.

> **Project status:** The web application was brought to a working state
> during testing. Cloud monitoring and operational improvements are
> ongoing. This document describes the architecture and challenges
> encountered; it does not claim that every production-readiness task is
> complete.

##  What does the project do?

-   Displays handmade craft products in a web browser.
-   Allows customers to register and log in.
-   Allows logged-in customers to place orders.
-   Stores users and orders in Amazon DynamoDB.
-   Retrieves the authenticated customer's order history.
-   Uses Amazon CloudWatch for logs and infrastructure monitoring.

##  Architecture
![alt text](<CraftNest AWS Architecture Overview.png>)

### AWS services

  |Service                     |        Role|
  |-|-|
  |mazon S3                    |       Hosts the static frontend files.|
|Amazon API Gateway              |   Provides HTTP API endpoints for the frontend.|
|AWS Lambda             |             Runs the Python backend without managing a server.|
 | Amazon DynamoDB            |         Stores customer and order data.|
|Amazon CloudWatch         |          Collects logs and service metrics provides monitoring dashboards.|
|AWS IAM                 |            Controls which AWS resources the Lambda execution role can access.|


<h3> Main API endpoints</h3>

  |Method  |                Endpoint   |             Purpose|
  |-|-|-|
  |`POST`                 | `/register`           |  Creates a customer account.|
  |`POST`           |       `/login`            |    Authenticates a customer and returns a session token.|
  |`POST`         |         `/orders`         |      Creates an order for the authenticated customer.|
  |`GET`        |           `/orders`        |       Retrieves the authenticated customer's orders.|


The frontend sends requests to API Gateway. API Gateway invokes Lambda,
and the backend reads from or writes to DynamoDB.






##  Important configuration

### Lambda environment variables

The backend is designed to read table names from environment variables:

``` text
USERS_TABLE=UsersTable
ORDERS_TABLE=OrdersTable
```

Use the exact table names in your AWS account and region. Other
environment variables may be required by the deployed backend version,
such as a session-signing secret and CORS allowed origin. 

### IAM execution role

Lambda uses an IAM execution role when it accesses AWS services. Typical
DynamoDB permissions for this project include:

-   `dynamodb:PutItem` -- create user or order records.
-   `dynamodb:GetItem` -- retrieve a user record.
-   `dynamodb:Query` -- retrieve a customer's orders through the GSI.

The policy resource ARNs must refer to the real table and index names,
account, and region. Use least-privilege permissions. A Lambda
administration policy does not automatically grant the function
permission to write to DynamoDB.

##  CORS -- a common integration challenge

**CORS** means Cross-Origin Resource Sharing. Browsers enforce it when a
frontend hosted at one origin (for example, an S3 website or CloudFront
domain) calls an API hosted at another origin (API Gateway).

A request may reach the API, but the browser can block the frontend from
reading the response if CORS is not configured correctly.

Check that:

1.  API Gateway allows the actual frontend origin.
2.  Allowed methods include those used by the app, such as `GET`,
    `POST`, and `OPTIONS`.
3.  Allowed headers include `Content-Type` and `Authorization` when
    bearer-token authentication is used.
4.  Backend CORS response headers agree with API Gateway configuration.
5.  The allowed origin matches the deployed frontend origin. Do not use
    a temporary S3 presigned URL as a permanent allowed origin.

CORS is not authentication or authorization; it is a browser security
policy controlling cross-origin access.

##  Challenges encountered and lessons learned

These are troubleshooting lessons encountered while bringing the project
together.

### Challenge 1: Registration returned HTTP 500 -- IAM permission denied

**Observed error:**

``` text
AccessDeniedException
when calling the PutItem operation:
not authorized to perform dynamodb:PutItem
```

**Cause:** The Lambda execution role did not have permission to write to
the DynamoDB Users table.

**How to investigate and fix:** - Identify the execution role attached
to Lambda. - Inspect its attached and inline IAM policies. - Allow the
required DynamoDB action on the correct table ARN. - Check the actual
table name, account ID, and region. - Retry registration and inspect the
new CloudWatch log.

### Challenge 2: DynamoDB table-name mismatch

**Observed situation:** Backend configuration or IAM policy referred to
names such as `CraftNestUsers` and `CraftNestOrders`, while the actual
tables were named:

``` text
UsersTable
OrdersTable
```

**Cause:** Names used by backend configuration, IAM policies, and
DynamoDB did not match.

**Lesson / fix:** - Confirm exact names in DynamoDB. - Set `USERS_TABLE`
and `ORDERS_TABLE` in Lambda environment variables. - Ensure IAM
resource ARNs use those exact names. - Keep the names consistent across
all layers.

### Challenge 3: GET `/orders` returned HTTP 500 -- missing GSI

**Observed error:**

``` text
ValidationException:
The table does not have the specified index: user_email-index
```

**Cause:** The backend queried an index called `user_email-index`, but
the Orders table did not have an index with that exact name.

**Lesson / fix:** - Open `OrdersTable` → **Indexes** in DynamoDB. -
Check whether the expected GSI exists. - Create or correct it to match
the backend query: - Index name: `user_email-index` - Partition key:
`user_email` (String) - Sort key: `created_at` (String), if required by
the code. - Wait until the index status is **Active**. - Ensure order
items contain the index key attributes.

A GSI only indexes items that contain the required index key attributes.

### Challenge 4: Understanding HTTP 500 using CloudWatch

The browser console showed a failed API request with HTTP 500. The
browser identifies the failed request, but CloudWatch logs usually
provide the underlying AWS or application exception.

A useful debugging sequence:

1.  Browser Developer Tools → Network: inspect the failing request,
    response, and status.
2.  API Gateway: check whether the request reached the integration.
3.  Lambda: inspect invocation and execution details.
4.  CloudWatch Logs: read the exception and stack trace.
5.  IAM and DynamoDB: verify permissions, table names, keys, and
    indexes.

This helps distinguish a frontend problem from a backend or AWS
configuration problem.

### Challenge 5: Lambda Errors metric did not tell the whole story

A Lambda function can catch an application exception and return HTTP
500. Lambda may still record the invocation as successful if the
exception does not escape the handler.

**Lesson:** Monitor both: - Standard Lambda metrics: `Invocations`,
`Errors`, `Duration`, and `Throttles`. - Application error logs, such as
structured events where `event_type` is `UNHANDLED_EXCEPTION`.

A CloudWatch Logs metric filter can turn matching application log events
into a custom metric.

##  CloudWatch monitoring plan


A dashboard alone does not guarantee monitoring is complete. Configure
alarms for important failure conditions, test their actions, and verify
that notifications reach the intended recipient.



## takeaway

The most valuable part of this project is not just getting the website
to work. It is learning how to understand the complete request flow,
identify which AWS service is responsible when something fails, read
CloudWatch logs, correct IAM and database configuration, and monitor the
infrastructure.

**CraftNest is a practical starting point for learning AWS serverless
architecture and the troubleshooting mindset used in cloud and DevOps
engineering.**
