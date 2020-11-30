# Project-planning-datascience-challenge
Solution to a Data Science challenge aimed at optimising project planning in an industry

1. CONTEXT

Imagine an Oil &amp; Gas operator with a portfolio of projects to execute, faced with the decision on _how to sequence__these_ in time. Each project has _project attributes_ such as a production profile (correlating with how much revenuewill be generated over time), a maturity (indicating from when onwards a project is ready for execution), and the type of hydrocarbon that will be produced (Oil or Gas).

1. BUSINESS QUESTION

How to _optimally plan this sequence of projects,_ i.e. _in what sequence should I execute which projects from my__total portfolio of available projects_?

1. GIVEN

Assume the following:

3.1 PORTFOLIO

A portfolio with projects to be planned is provided here as an Excel table

Every project has the following properties:

- its name
- whether it&#39;s an Oil or Gas project
- the earliest date the project can be executed (&#39;earliest spud year&#39;)
- how long it takes to execute (&#39;duration&#39;)
- its production profile (how much Oil/Gas is produced, i.e. how much revenue will this project generate)

All projects are assumed to have the same cost profile.

Note: The earliest spud year is not necessarily the year of execution – it&#39;s the _earliest possible_ year of execution. (The actual year of execution is a variable to be optimized by you.)

3.2 OPTIMIZATION

To address the business question, please consider the following scenarios:

- Scenario 1: optimize the project sequence for maximum Oil production in 2021-2025.
- Scenario 2: optimize the project sequence for maximum Oil production in 2021-2025 with a desire that gas remains as long as possible around 1M m3/d from 2021 onwards.

1. DELIVERABLE

Design one or more approaches that are capable of addressing the business question. Demonstrate the efficiency &amp; robustness of your approach(es).
