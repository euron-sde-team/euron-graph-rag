# Walkthrough

A guided tour of the demo project with what to look at on each page. Run `make up && make demo`
first and sign in as `maya.iyer@meridian-research.example`.

## 1. Overview

The six counters (documents, passages, entities, relations, communities, questions) come from
the real pipeline. "The graph at a glance" shows the most important entities coloured by
community; the bars show entities by type and the most common relation verbs; the area chart is
two weeks of questions. The build card shows the latest graph build, what it merged and how
modular the partition was.

## 2. Documents

Eighteen notes, each with five pips for its journey (queued, parse, embed, extract, graph).
Open one: its passages are exactly the units that were embedded and cited, and "Strongest
entities" links into the explorer. Add a note with **Add documents, Text** and watch the row
move; when it is ready its entities are in the graph. Delete it and they leave again, along
with relations only it supported.

## 3. Graph explorer

Node size is importance (connections and mentions), colour is the entity type (switch to
community colours to see the clusters). Click a node: the panel lists what it is, how it
connects (outgoing and incoming relations, each with the sentence that stated it) and the
passages that mention it. Double-click, or press Enter on a selected node, to show only its
neighbourhood; the filter chip brings the whole graph back. Drag nodes, scroll to zoom, filter
by type or text.

## 4. Entities

The table behind the graph: search, filter by type, sort by importance, mentions, name or type.
The Duplicates tab lists what the next build would merge and why; after a build it is empty
because the build already merged them ("Helios" is an alias of "Helios Robotics"). Editors can
rename, retype, merge and delete.

## 5. Communities

The hierarchy: eight communities at level 0, each splitting into sub-communities. Every one has
a report: a summary, findings that each cite the passages behind them, and its members. Global
search reads these reports.

## 6. Playground

- **Local**: "Who founded Helios Robotics?" The answer quotes the passage; the chips link to the
  source cards; the subgraph shows the seed entities (ringed) and their neighbours; the trace
  lists the steps with timings.
- **Global**: "How is predictive maintenance used in port terminals?" The trace shows the map
  step over community reports and the reduce step; the sources are reports, and each says how
  many passages back it.
- **Hybrid**: "How does Helios Robotics depend on its suppliers and investors?" Passages and
  reports together.

Open **Recent questions** to replay any past answer.

## 7. Settings

Graph pipeline options (entity types, chunk size, hierarchy depth, resolution, automatic
builds), members and roles, API keys with copy-paste examples, and the activity trail.
