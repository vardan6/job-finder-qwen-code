# Role Description — Vardan Arakelyan, Software Engineer at Silvaco

## Role Overview

My role as a Software Engineer at Silvaco spans engineering infrastructure, QA, automation, and close collaboration with R&D and FAE teams. I have a background in circuit and system design, which gives me domain context that directly supports SmartSpice testing and customer issue work. Over time, my focus has grown more heavily toward process development, CI/CD, QA architecture, and internal tooling — areas where I have built strong expertise and where I contribute most consistently. Alongside this, I remain actively involved in customer issue reproduction, debugging, and research — working with R&D and FAE to define hypotheses, automate test cases, and analyze results.

---

## Routine Responsibilities

These recur on a regular cadence and require consistent tooling and scripting support:

- **Daily Build and Daily QA** — Linux and Windows platforms
- **Release Build and Release QA** — coordinated with product release cycles
- **Weekly Valgrind QA runs** — tracking memory errors across Valgrind reports, comparing unique error stacks between versions
- **Weekly Sanitizer QA runs** — monitoring runtime errors, ASAN and UBSAN error findings, and tracking resolution status
- **Periodic Code Coverage generation** — running coverage builds after releases, collecting and aggregating results across SmartSpice and its libraries, and maintaining the reporting pipeline
- **GitHub administration and maintenance** — shared responsibility with Scott; includes organization and repository management, access control, and platform health on the GitHub Enterprise Server (cagit02)

---

## Strategic and Ongoing Work Areas

### CI/CD Governance and Quality Engineering

Designing and maintaining automated quality gates in the CI/CD pipeline. This includes enforcing code quality standards through automated checks that prevent regressions from entering the main branch. Work spans pipeline architecture, script development, and long-term maintenance.

### QA Architecture — New QA System

An ongoing, multi-phase redesign of the QA workflow for SmartSpice. Key design principles already established: self-contained test cases and an interactive test-runner with live monitoring. Work in progress includes efficient data aggregation, grouping and filtering for faster analysis, and performance and scalability validation. Migration of existing test suites to the new system is underway. Web-based reporting needs to be fully implemented, though a basic HTML dump for test cases is already available. A database architecture is in progress to support better data dumping, monitoring, and reporting.

### Code Coverage

Periodic generation and analysis of code coverage reports across SmartSpice and its libraries after releases. Involves running coverage builds, collecting and aggregating results, and maintaining the reporting pipeline. Ongoing work includes tooling upgrades and expanding coverage to additional test suites.

### Performance Testing Infrastructure

Designing a new test suite, infrastructure, and framework dedicated to performance testing. This includes defining test case structure, measurement methodology, and tooling to make performance validation repeatable and comparable across versions.

### Windows QA Stability and Performance

Investigating and resolving reliability and performance issues in the Windows QA environment, including significant overhead caused by platform-specific tooling. Involves debugging, profiling, and scripting improvements.

### Sanitizer Reporting Improvements

Enhancing the reporting pipeline for Sanitizer QA results, making findings easier to review and track over time. Need to develop newer more complete web based reporting.

### Repository and Infrastructure Orchestration

Managing large-scale migrations of repositories between GitHub Enterprise instances (cagit01 → cagit02), ensuring asset availability, and maintaining CI/CD infrastructure documentation on Wiki and GitHub Pages.

---

## Skills and Supporting Capabilities

### Automation and Scripting

Development of automation scripts and tools in Python, Shell/Bash, and YAML (GitHub Actions). Also supports and maintains legacy Perl and C-shell scripts. Focus is on rapid, reliable implementation — the goal is to solve the problem quickly and correctly, not to produce production-grade product code. This is a primary area where AI assistance provides high value.

### Test Automation and Data Analysis

Writing automation flows to generate parameterized input data, run SmartSpice in parallel, monitor execution state, and collect results. Applying data science skills to practical engineering tasks: parsing structured and unstructured output, aggregating metrics, filtering and grouping results, and generating actionable summaries. Uses Bash and Python-based tooling.

### Web-Based Reporting and Internal Tools

Building small to medium web servers and dashboards that surface QA results, GitHub data, and engineering metrics in a browser-accessible format. Includes automatic status email notifications for key QA events. The longer-term goal is to consolidate all QA and automated testing results under a unified web reporting structure, providing a single place to monitor all pipelines, test runs, and coverage data. These tools integrate with SharePoint, GitHub Enterprise, and internal Wiki systems, making information accessible to developers and managers without requiring direct system access.

### Customer Issue Investigation and R&D Collaboration

Reproducing customer-reported issues in-house and working directly with R&D and FAE on investigation and resolution. This involves replicating customer environments, defining hypotheses, and running targeted tests to confirm or rule out root causes — covering crashes, memory and disk instability, licensing failures, and runtime anomalies. Beyond reproduction, automation is designed around these scenarios to make coverage repeatable and efficient.

### Documentation

Writing Wiki pages, solution proposals, discussion comments, issue descriptions, and process documentation. Covers both technical implementation details and process descriptions for team reference.

### Circuit Design Background

Strong background in schematic and system design. Provides domain context useful for understanding SmartSpice test scenarios, customer circuit use cases, and PDK-based testing tasks.

