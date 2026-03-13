# ZaikaNow System Architecture

## Overview

ZaikaNow is an India-native food delivery marketplace serving major metros such as Bengaluru, Mumbai, Delhi NCR, Hyderabad, Pune, and Chennai.

The platform runs on a microservice architecture in AWS ap-south-1 (Mumbai), with PostgreSQL, Redis, and external payment integrations.

## Core Services

### Catalog Service
- Manages restaurants, menus, cuisine rails, and city-specific discovery collections.

### Search Service
- Powers search, ranking, and repeat-order recommendations.

### User Service
- Handles authentication, profiles, addresses, and customer support linkage.

### Checkout Service
- Owns cart state, order creation, and payment orchestration.

### Payment Service
- Manages online payments across UPI, cards, wallets, and COD reconciliation.
- Recently migrated from RupeeFlow v2 to RupeeFlow v3 on January 10, 2025.

### Notification Service
- Sends order updates, payment alerts, and support-related notifications.

## Payment Path

1. Customer taps `Place Order`
2. Checkout Service creates the order intent
3. Payment Service creates a RupeeFlow transaction
4. Customer approves UPI in their banking app or wallet flow
5. RupeeFlow sends async confirmation callback
6. ZaikaNow confirms the order and notifies the customer

## Failure Pattern Under Investigation

- After the RupeeFlow v3 migration, callback confirmation became unreliable for a subset of UPI flows
- Android users in high-volume metros were hit hardest
- Some users saw money debited or approval completed, but order confirmation never resolved cleanly

## Infra Notes

- Primary AWS location: ap-south-1 (Mumbai)
- Databases: PostgreSQL (Multi-AZ), Redis for cache and queue coordination
- Monitoring: Datadog dashboards and alerting
- Logs: CloudWatch and centralized error aggregation
