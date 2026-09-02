# 0.2.0
## 2026-09-02

1. [](#new)
    * Declared compatibility with both Grav 1.7 and Grav 2.0. Without a `compatibility` block Grav 2.0 infers a single version from the `grav` dependency, which would have made this plugin 2.0-only by omission
    * `languages.yaml`, so the plugin's settings in the admin panel can be translated rather than being English by construction
2. [](#improved)
    * End-to-end tests boot a real Grav on both supported lines, and browser tests drive the filtering; both run in CI against the newest release on each line
3. [](#bugfix)
    * Filtering the hierarchy by Done or Cancelled showed nothing at all unless "show done and cancelled" happened to be ticked. Choosing a status now overrides that toggle
    * The hierarchy's empty state named `/backlog` rather than the configured backlog route, which was wrong for exactly the sites most likely to be reading it

# 0.1.0
## 2026-09-02

1. [](#new)
    * Hierarchy view: epics with their stories, collapsible, filterable by status and label, searchable, ordered by global rank
    * Priority-by-person view: open stories somebody could pick up, in rank order, filtered to the labels they can work on
    * Configurable backlog route, roster route and front-matter namespace
    * Pages opt in through front matter, so both views degrade to ordinary pages when the plugin is disabled
