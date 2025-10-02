# Instagram Comment Moderation and Filtering Platform

This repository contains the source code for a high-performance, AI-powered SaaS platform designed to help Instagram creators automatically moderate and filter comments on their posts and reels. The system leverages a Large Language Model (LLM) to classify incoming comments and applies user-configurable rules to manage them in near real-time, ensuring a safe and positive community environment.

This project was specified by Kartik, and the SRS document provides a comprehensive, developer-ready plan including architecture, data models, APIs, and operational details[cite: 4].

## 🚧 Under Development

This project is currently under active development. The Software Requirements Specification (SRS) is complete, and implementation is in progress based on the architecture and details outlined in this document. Please refer to the project's issue tracker and version control history for the latest updates on feature completion and release timelines.

-----

## 📑 Table of Contents

- [✨ Key Features](#-key-features)
- [🛠️ Tech Stack](#-tech-stack)
- [🏗️ Architecture & Core Concepts](#-architecture--core-concepts)
  - [Comment Processing Workflow](#comment-processing-workflow)
  - [Data Model Highlights](#data-model-highlights)
  - [LLM Prompting Strategy](#llm-prompting-strategy)
- [📦 API Endpoints](#-api-endpoints)

-----

## ✨ Key Features

* **AI-Powered Classification**:

  * Utilizes GPT-40 Mini (or an equivalent LLM) for nuanced comment classification[cite: 8, 324].
  * For paid users, a Vision API (like Gemini) analyzes reels to generate a rich context summary and relevant topics, enhancing moderation accuracy[cite: 8, 53].

* **Granular & Customizable Filter Rules**:

  * Creators can establish global filter settings that apply to all their content[cite: 14, 56].
  * For specific content, users can override global settings with per-post filters, allowing for tailored moderation strategies[cite: 14, 57]. When a post is first seen, global filters are cloned to create a local copy that can be modified independently[cite: 57].

* **Near Real-Time Moderation**:

  * An asynchronous architecture using Celery and Redis processes comments almost instantly after they are posted[cite: 8, 321].
  * The system is designed to be reliable, providing near-real-time classification and optional deletion of comments[cite: 12].

* **Aggressive Cost Optimization**:

  * **ToneCache**: A Redis-based cache stores classification results for identical comments on similar post contexts, drastically reducing redundant LLM calls[cite: 9, 71]. The cache key is a hash of the post's context and the normalized comment text[cite: 70].
  * **Single Summary Generation**: To minimize token usage, a context summary for each post or reel is generated only once upon the arrival of the first comment[cite: 13, 51].

* **Scalable & Resilient by Design**:

  * The architecture is built to handle sudden spikes in comment volume, such as on viral posts, using robust Redis-based queuing and locking mechanisms[cite: 16, 64, 65].
  * A Dead Letter Queue (DLQ) system captures tasks that fail after multiple retries (e.g., an API call to delete a comment), ensuring data integrity and allowing for manual intervention[cite: 15, 90, 91].

* **SaaS Model with Trials & Usage Quotas**:

  * New users receive a 14-day free trial with access to all features[cite: 7, 38, 39].
  * The trial is limited to AI analysis on 10 posts and 3 reels to manage costs[cite: 7, 40]. After the trial, the account becomes read-only and is eventually blocked unless the user subscribes[cite: 8, 42, 43].
  * Paid plans are quota-based (e.g., 100 comments/day, 1000 comments/day)[cite: 44, 46, 47]. Quotas are enforced using a precise sliding-window algorithm implemented in Redis ZSETs[cite: 9, 83].

-----

## 🛠️ Tech Stack

The system is built with a modern, scalable, and cost-effective technology stack [cite: 319-329].

| Component              | Technology                                                     |
| ---------------------- | -------------------------------------------------------------- |
| **Backend**            | Python 3.11, Django 4.x, Django REST Framework [cite: 320]    |
| **Asynchronous Tasks** | Celery 5.x with a Redis broker and result backend [cite: 321] |
| **Database**           | PostgreSQL 13+ with PgBouncer for connection pooling [cite: 323] |
| **Cache & Locking**    | Redis 6/7 [cite: 322]                                         |
| **AI / Machine Learning** | GPT-40 Mini API, Gemini Vision (or similar) [cite: 324, 325] |
| **Payments**           | Razorpay [cite: 326]                                           |
| **Hosting**            | Dockerized; suitable for AWS, GCP, or DigitalOcean [cite: 327] |
| **Monitoring**         | Prometheus, Grafana, and Sentry for errors [cite: 328]        |

-----

## 🏗️ Architecture & Core Concepts

The system's architecture is event-driven and asynchronous, designed for high throughput and reliability.

### Comment Processing Workflow

1. **Ingestion**: An Instagram webhook sends new comment data to a Django REST API endpoint[cite: 62]. The endpoint verifies the signature and returns a `202 Accepted` immediately[cite: 244].
2. **Enqueue**: The comment payload is enqueued into a Celery task queue for background processing[cite: 62].
3. **Context Generation**: A worker picks up the task[cite: 63]. If it's the first comment on a post (`summary_generated` is false), the worker attempts to acquire a Redis lock (`SETNX`)[cite: 64]. If successful, it generates and stores a context summary of the media exactly once[cite: 64]. Other comments for the same post are temporarily held in a Redis list until the summary is ready[cite: 65].
4. **Quota Check**: The system checks if the user is within their daily comment processing limit using a Redis ZSET-based sliding window[cite: 84]. If the limit is exceeded, the comment is stored but not processed further[cite: 86].
5. **Classification**: The comment is classified using the LLM. The system first checks the `ToneCache` in Redis[cite: 71]. If it's a miss, a compact, cost-optimized prompt is sent to the LLM[cite: 72].
6. **Action**: The LLM's response (`tone_name`, `delete_flag`) is matched against the user's filter rules, checking the `POST_TONE_FILTER` table first, and falling back to `USER_GLOBAL_TONE_FILTER`[cite: 75, 76]. If the final decision is to delete, the system calls the Instagram Graph API[cite: 77].
7. **Error Handling**: If the Instagram API call fails, the deletion task is pushed to a DLQ for retry[cite: 78].

### Data Model Highlights

* **Users**: Stores user account info, plan type (`trial`, `paid`, `read_only`), and trial status [cite: 95-105].
* **SocialAccounts**: Securely stores encrypted OAuth tokens for linked Instagram accounts[cite: 108, 113].
* **Posts**: Contains metadata for each post/reel, including the generated context summaries and topics[cite: 118, 125, 126, 127].
* **Comments**: Stores each comment, its parent (if it's a reply), the classification result (`tone_integer`), and the action taken[cite: 131, 135, 137, 139].
* **USER_GLOBAL_TONE_FILTER**: Stores a user's default moderation rules[cite: 142].
* **POST_TONE_FILTER**: Stores post-specific overrides for the moderation rules[cite: 150].
* **DLQ**: A dedicated table to log and manage failed asynchronous tasks for later inspection and retry[cite: 178].

### LLM Prompting Strategy

To control costs and ensure consistent responses, a strict prompting strategy is used[cite: 267].

* **Principle**: Use minimal context, request integer or boolean outputs, and enforce a compact, single-line JSON structure in the response[cite: 268, 277, 280].
* **Context**: Always pass the pre-computed 8 or 12-word summary instead of the full media caption to reduce input tokens[cite: 281].
* **Example Classification Prompt**:

```json
{
  "Context": "[context_summary]",
  "Topics": ["topic1", "topic2"],
  "Parent": "[parent_comment_text]",
  "Comment": "[comment_text]",
  "Instruction": "Return only JSON single line: {\"tone_integer\":<int>, \"tone_name\":\"<label>\",\"delete_flag\":<0|1>}"
}
````

---

## 📦 API Endpoints

The service exposes a RESTful API built with Django REST Framework[cite: 232]. All endpoints require JWT or session authentication unless specified otherwise[cite: 233].

| Group               | Endpoint                            | Description                                                               |
| ------------------- | ----------------------------------- | ------------------------------------------------------------------------- |
| **Authentication**  | `POST /auth/signup`                 | Register a new user with email[cite: 235].                                |
|                     | `POST /auth/login`                  | Log in and receive an auth token[cite: 237].                              |
| **Account Linking** | `GET /instagram/connect`            | Initiates the OAuth flow to link an Instagram account[cite: 241].         |
|                     | `POST /instagram/callback`          | Handles the OAuth callback to store tokens securely[cite: 242].           |
| **Webhooks**        | `POST /webhooks/instagram/comments` | Ingests new comments from Instagram[cite: 244].                           |
|                     | `POST /webhooks/razorpay`           | Processes payment events from Razorpay[cite: 260].                        |
| **Moderation**      | `GET /posts/{post_id}`              | View post details and its specific filter settings[cite: 247].            |
|                     | `POST /posts/{post_id}/filters`     | Add or update tone filters for a specific post[cite: 250].                |
|                     | `GET /posts/{post_id}/comments`     | List comments for a post with their classification and status[cite: 252]. |
| **Admin**           | `GET /admin/dlq`                    | List tasks in the Dead Letter Queue[cite: 262].                           |
|                     | `POST /admin/dlq/{id}/retry`        | Re-queue a failed task from the DLQ for processing[cite: 263].            |

---



