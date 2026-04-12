**Backend Audit And Plan**

# **Scope**

* backend repository only

* current Python code, application config, dependency manifest, and runtime structure

# **Executive Summary**

The backend is functional, but it is not production-safe in its current form.

The biggest issues are:

* unsafe fallback secrets and silent development defaults in configuration

* payment card design stores CVV data in the database

* the main app and route layer are too large, which increases change risk and makes testing difficult

* dependencies are unpinned, duplicated, and mixed across main API, chatbot, reporting, and optional AI workloads

* there is no visible backend test suite and no enforced PR quality gate

* the current single-EC2 operating model is too exposed, especially after the mining compromise

# **Current Audit Notes**

## **1\. Critical: Configuration Falls Back To Unsafe Defaults**

**Evidence:**

* config.py:11 uses dev\_key\_not\_for\_production

* config.py:16 uses a hardcoded local database URL fallback

* config.py:34 uses jwt\_dev\_key\_not\_for\_production

* config.py:70 uses a fallback exchange-rate API key

* config.py:92-93 use fallback Razorpay test credentials

* config.py:122-127 defaults to DevelopmentConfig when FLASK\_ENV is missing

**Risk:**

* production can boot with insecure settings if environment variables are absent or misconfigured

* incident recovery becomes unreliable because the runtime behavior is not strict

**Required Direction:**

* remove all secret and credential fallbacks

* fail fast when required environment variables are missing

* default to production-safe behavior, not development mode

## **2\. Critical: CVV Is Being Stored In The Database**

**Evidence:**

* models/payment\_card.py:20 defines encrypted\_cvv

* models/payment\_card.py:82-86 persists CVV

* models/payment\_card.py:104-106 supports decrypting stored CVV

* controllers/payment\_card\_controller.py:40 sets the CVV on card creation

**Risk:**

* CVV must not be retained after authorization

* encryption does not make this acceptable from a payment-security perspective

* this is a much higher risk than most ordinary application bugs

**Required Direction:**

* remove CVV persistence completely

* use tokenized payment flows instead of storing sensitive card secrets

* reassess the entire card-storage design before keeping this module in production

## **3\. High: Card Encryption Key Handling Is Unsafe And Can Break Data Recovery**

**Evidence:**

* config.py:71 defines CARD\_ENCRYPTION\_KEY from environment only

* init\_db.py:362-368 generates a new Fernet key if one is missing

**Risk:**

* encrypted data can become unreadable if the key is regenerated

* startup behavior becomes inconsistent across environments

* secret generation inside initialization logic is not acceptable for persistent encrypted data

**Required Direction:**

* require a stable key from Secrets Manager or Parameter Store

* never generate a new production encryption key inside app initialization

* rotate keys through a controlled migration plan only

## 

## **4\. High: The Application Entrypoint Is Too Large And Overloaded**

**Evidence:**

* app.py is about 1066 lines

* routes/superadmin\_routes.py is about 6241 lines

* routes/merchant\_routes.py is about 5440 lines

* controllers/reels\_controller.py is about 2649 lines

**Risk:**

* high regression risk on small changes

* difficult onboarding and review

* weak separation of concerns

* low testability

**Required Direction:**

* split app bootstrapping from route registration, middleware, monitoring, and error handling

* break route modules by bounded domains

* move business logic out of route files into services and use-cases

## **5\. High: Dependency Management Is Weak**

**Evidence from requirments.txt:**

* all packages are unpinned

* duplicate entries exist for flask, flask-cors, requests, waitress, and psutil

* one manifest mixes core API packages, reporting packages, chatbot packages, and optional AI packages

**Examples:**

* both mysql-connector-python and pymysql are present even though config uses mysql+pymysql

* both waitress and gunicorn are present for server startup paths

* fastapi and uvicorn are in the same manifest as the Flask API

* pytest is in the production dependency list even though there is no visible test suite

* psycopg2-binary is present while the main backend config is MySQL-oriented

**Risk:**

* non-reproducible builds

* package drift between environments

* unclear package ownership

* larger attack surface and slower incident recovery

**Required Direction:**

* replace requirments.txt with pinned dependency sets

* split dependencies into:

* main API runtime

* chatbot or AI runtime

* development and test tools

* standardize on one MySQL driver

* standardize on one production WSGI strategy

## **6\. High: Dependency Ownership Needs Cleanup**

Current code indicates these packages should be declared explicitly if they remain in the repository runtime:

* cryptography

* pydantic

* celery

* langchain-core

Current package review also shows some packages need manual verification before keeping them in the main backend runtime:

* psycopg2-binary

* stripe

* pytest

* transformers

* sentence-transformers

* faiss-cpu

* huggingface\_hub

**Important Note:**

* some packages are needed indirectly even without direct imports

* for example, openpyxl, xlsxwriter, and FAISS-related packages may still be runtime dependencies through pandas or LangChain integrations

* these should be reviewed by workload, not removed blindly

## **7\. High: No Visible Backend Test Suite Or PR Quality Gate**

**Evidence:**

* no tests/ directory found

* no pytest.ini or tox.ini found

* no visible backend CI workflow found in the repository

**Risk:**

* changes can ship without behavioral verification

* dependency updates cannot be trusted

* production regressions are likely

**Required Direction:**

* add backend unit tests

* add create-app smoke tests

* add authentication, cart, order, payment, and admin regression tests

* require these checks on every pull request

## **8\. High: API Exposure Is Broader Than It Should Be**

**Evidence:**

* app.py:95-101 defines a static ALLOWED\_ORIGINS list in code

* app.py:167 exposes API docs at /docs

* chatbot.py:32-36 has a separate static origin list

* chatbot.py:240 runs a public Flask app directly

**Risk:**

* environment-specific security policy is embedded in source

* production docs may expose internal surface area

* duplicated CORS policy increases drift

**Required Direction:**

* move allowed origins to environment configuration

* disable or protect API docs in production

* standardize security headers and CORS behavior across services

## **9\. Medium: Cache Strategy Is Inconsistent With The Codebase And Planned Infra**

**Evidence:**

* config.py:45 sets CACHE\_TYPE \= 'null'

* app.py:246 forces CACHE\_TYPE to null at startup

* common/cache.py still contains a Redis client helper with fallback to redis://localhost:6379/0

* several services and decorators still contain Redis-aware code paths

* recommendation, auth, follow, reels, and decorator-based cache or rate-limit flows generally degrade gracefully when Redis is missing

* translation code still builds a Redis-backed service object and is not safely guarded if Redis is absent while translation is enabled

**Risk:**

* ElastiCache would add cost without value in the current application behavior

* developers can assume caching exists when it does not

* teams can incorrectly conclude that Redis is fully unused, even though some runtime paths still try to access it

* one optional feature path can still fail if Redis is unavailable

**Required Direction:**

* document the current state accurately as: Redis is disabled by default for the main backend, but Redis-aware code still exists

* either fully disable Redis code paths for now

* or re-enable caching intentionally with clear ownership, key design, TTL policy, and monitoring

* fix translation-service behavior so it does not assume Redis exists when the feature is enabled

## **10\. Medium: Current Backend Is Not Safely Scale-Ready Or Zero-Downtime Ready**

**Evidence:**

* app.py:821-874 starts a BackgroundScheduler inside the web application process

* app.py:854-860 schedules notification cleanup in-process instead of as a separate worker or scheduled job

* app.py:440-456 and app.py:676+ provide health endpoints, but there is no clear readiness, graceful-drain, or shutdown handling strategy in the app itself

* app.py:891-1062 still contains mixed startup behavior and fallback server logic inside the application entrypoint

* no visible backend test suite or rollout verification pipeline exists to prove safe rolling deployments

**Risk:**

* if multiple instances are started, each instance can start its own scheduler and duplicate background work

* horizontal scaling can create inconsistent operational behavior

* rolling deploys are possible at the infrastructure layer, but not confidently safe from the application side

* zero-downtime deployment is not credible without readiness checks, graceful shutdown, migration discipline, and deployment smoke tests

**Required Direction:**

* move scheduled cleanup out of the web process into a separate worker, cron-style task, or platform scheduler

* treat the web application as stateless request-serving only

* add proper readiness and graceful-shutdown behavior

* require backward-compatible database migrations for rolling deployments

* require post-deploy smoke checks before considering zero-downtime rollout support complete

## 

## 

## **11\. Medium: Error And Operational Logging Need Tightening**

**Evidence:**

* app.py:609-645 logs full stack traces and stores monitoring records

* chatbot.py:215 returns traceback.format\_exc() in API error responses

* services/s3\_service.py prints detailed upload internals to stdout

**Risk:**

* stack traces can leak implementation detail

* logs may include internal object keys and operational metadata

* noisy logs increase incident response time

**Required Direction:**

* return sanitized client errors

* keep full traces in restricted logs only

* replace ad hoc print() debugging with structured logging

* redact secrets, tokens, and sensitive identifiers

## **12\. Medium: Repository Hygiene Is Poor Inside The Backend Repo**

**Evidence:**

* duplicate trees exist: .git 2, auth 2, common 2, controllers 2, routes 2

* duplicate file exists: requirments 2.txt

**Risk:**

* accidental imports or packaging confusion

* review noise

* harder incident recovery and ownership tracking

**Required Direction:**

* remove duplicate trees and keep one source of truth

* clean import paths after the duplicate content is removed

# **Sanity Check Result**

* python \-m compileall \-q . completed successfully inside the backend virtual environment

* this only confirms syntax-level loadability

* it does not confirm runtime correctness because there is no real test suite yet

# 

# **Backend Plan**

## **Phase 1: Security Fixes First**

* remove all fallback secrets and credentials from config.py

* make ProductionConfig fail fast if required settings are missing

* stop storing CVV data

* stop generating encryption keys during initialization

* move all secrets to AWS Secrets Manager or SSM Parameter Store

* move origin allowlists and docs exposure to environment-driven configuration

* sanitize chatbot and API error responses

## **Phase 2: Structure And Maintainability**

* split app.py into:

* app factory

* extension wiring

* security and middleware

* error handling

* blueprint registration

* startup entrypoints

* split routes/superadmin\_routes.py and routes/merchant\_routes.py into smaller domain modules

* move business logic out of routes and controllers into service-layer functions

* isolate chatbot and optional AI workloads from the main Flask API runtime

* remove duplicate backend directories and stale files

## **Phase 3: Dependency And Compatibility Plan**

* create a pinned requirements.in for the main API

* compile a locked requirements.txt

* create separate requirement files for:

* chatbot or AI service

* development and testing

* standardize on one MySQL driver

* explicitly declare direct imports such as cryptography and pydantic

* keep only the packages needed by the main Flask API in the main production manifest

* treat report-export and AI packages as optional workloads if they are not part of every backend deployment

## 

## **Phase 4: Testing Plan**

* add pytest

* add app-factory smoke tests

* add auth tests

* add payment-card safety regression tests while removing CVV storage

* add cart and order tests

* add admin authorization tests

* add service tests for S3, Redis, and notification cleanup behavior

* add migration smoke tests for the DB schema

## **Phase 5: PR Gates And CI/CD Policy**

Every PR must run:

* backend dependency install from pinned requirements

* python \-m compileall \-q .

* unit tests

* linting with ruff

* formatting check with black \--check

* import sorting check

* pip-audit

* bandit

* secret scanning with gitleaks or detect-secrets

* dependency ownership check with deptry

* app startup smoke test for create\_app()

Fail the PR when:

* tests fail

* new critical or high vulnerabilities appear

* a module is imported directly but not declared explicitly

* unused runtime packages are added without justification

* a migration changes models without review notes

## **Phase 6: Deployment Policy**

* only deploy from reviewed pull requests

* block direct pushes to the production branch

* require green CI before deployment

* run smoke checks after deployment

* keep rollback capability at the release level

* separate environments for development, staging, and production

# **Cost-Effective Infra Recommendation**

## **Recommended Option**

For this backend, the best balance of security and operational simplicity is:

* frontend on S3 \+ CloudFront

* backend on ECS Fargate behind an ALB

* small private RDS for MySQL

* ElastiCache only after caching or queue usage is enabled intentionally

Why this is the best fit:

* the last incident was a compromised EC2 instance running mining software

* Fargate removes most direct server management and reduces host-level persistence risk

* it is easier to operate safely if you are the deployment owner and not the main backend developer

## **Lowest-Cost Acceptable Alternative**

If cost pressure is more important than operational simplicity:

* keep frontend on S3 \+ CloudFront

* run the backend on one small Graviton EC2 instance in an Auto Scaling Group

* use min=1, desired=1, max=2

* put the backend behind an ALB

* keep the instance in a private subnet if possible

* use Session Manager instead of SSH

## **Instance Right-Sizing**

* the current m6g.xlarge looks oversized on CPU from the graph you shared

* do not keep that size unless memory usage proves it is needed

* first right-size to t4g.large or m7g.large based on memory profile

* choose t4g.large if traffic is light and bursty

* choose m7g.large if the app needs steadier memory headroom

## **RDS And ElastiCache**

* start with a small private RDS instance

* enable backups, Performance Insights, and restore testing

* do not add ElastiCache immediately because the backend currently forces caching off

* add ElastiCache only after Redis caching, session storage, rate limiting, or worker queues are actually enabled and measured

## **Server Security Plan**

* rebuild from a clean base after the compromise

* rotate all secrets and keys

* remove the PEM file from shared workspaces and rotate it if it was ever used

* use Systems Manager Session Manager instead of open SSH

* disable password auth and direct root login

* enable GuardDuty, Inspector, Security Hub, and CloudTrail

* keep ALB public, backend private, and RDS private

* use least-privilege IAM roles

* enable encryption for EBS, RDS, and S3

* centralize logs and alert on unusual CPU, outbound traffic, auth failures, and 5xx spikes

## **DNS Recommendation**

* move DNS from GoDaddy to Cloudflare

* validate all records before cutover, especially mail-related records

* enable DNSSEC after migration

* use Cloudflare for DNS and edge protection

* keep CloudFront as the frontend CDN and do not create unnecessary double-caching complexity

# **Definition Of Done**

* no unsafe secret fallbacks remain in backend code

* CVV storage is removed

* encryption key handling is stable and externally managed

* the backend dependency set is pinned and separated by workload

* duplicate backend trees are removed

* app.py and oversized route modules are split into maintainable units

* backend tests exist and run on every PR

* PRs enforce audit, lint, vulnerability, secret, and package-usage checks

* backend deployment is immutable, review-gated, and rollback-safe

* the new infra footprint is smaller, safer, and easier to operate than the current single oversized EC2 model