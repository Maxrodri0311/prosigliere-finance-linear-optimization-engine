# 📐 SPEC & BLUEPRINT: Prosigliere Analytics Engineer Bridge Project (prosigliere-finance-linear-optimization-engine)

**Target Company:** Prosigliere | **Target Role:** Analytics Engineer  
**Delivery Paradigm:** `DeliveryParadigm.EXPLAINABLE_AI_INFERENCE`  
**Core Algorithm:** `AlgorithmFamily.LINEAR_PROGRAMMING`  
**Repository Name:** `prosigliere-finance-linear-optimization-engine`  

---

## 🏛️ 1. The Core Business Bottleneck
Prosigliere requires an enterprise-grade Causal & Survival Lifecycle Analytics architecture under Analytics Engineer to solve operational latency, resource allocation bottlenecks, and provide C-Level visibility.

---

## ⚖️ 2. Domain Entities & Key Variables

### Domain Entities
- **PrimaryExecutionUnit**: Core domain entity representing business transactions for Prosigliere (Primary Key: `prosigliere_ana_id`)
  - Attributes: `prosigliere_ana_id, primary_metric, is_active`

### Key Variables & Physical Distributions
- `primary_metric`: Semantic Type: `continuous` | Bounds: `(10.0, 500.0)`- `volume_count`: Semantic Type: `discrete` | Bounds: `(1.0, 1000.0)`- `is_active`: Semantic Type: `boolean`- `status_category`: Semantic Type: `categorical`
---

## 🎙️ 3. Interview Defense & Technical Edge

### ❓ Question 1: Why use AlgorithmFamily.LINEAR_PROGRAMMING instead of a naive heuristic or standard grouping?
> **💡 Strategic Answer:**  
> *"Traditional static models fail to capture Modelado Dinámico Temporal vs Agregaciones Estáticas Tradicionales. By implementing AlgorithmFamily.LINEAR_PROGRAMMING over a decoupled architecture, we achieve mathematically rigorous optimization while maintaining sub-150.0ms response times."*

### ❓ Question 2: How do you guarantee zero memory leaks and sub-150.0ms latency?
> **💡 Strategic Answer:**  
> *"Through vectorized columnar execution (DuckDB/Parquet) and strict Clean Architecture (DIP). Ingestion, domain models, and delivery interfaces communicate strictly through Protocols without vendor locking or hidden I/O bottlenecks."*