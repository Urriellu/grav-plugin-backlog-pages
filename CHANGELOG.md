# 0.3.0
## 2026-09-02

1. [](#new)
    * Blocked stories are marked with an emoji in both views, with the blockers named in the tooltip and a dashed left edge. Blocked is derived from `depends_on` rather than declared -- a story is blocked while anything it depends on is still open -- so nothing is marked by hand and nothing can go stale once the blocker closes
    * A **Ready only** toggle in both views, and a count of the blocked stories each is showing. The person view says outright when everything somebody could pick up is blocked, which is a different situation from nothing carrying their labels
2. [](#improved)
    * A `depends_on` key matching no story on the site counts as blocking. It cannot be shown to be finished, so this covers blockers outside the backlog and stops a typo reading as ready
    * The end-to-end checks assert the blocked markup on both supported Grav lines, and the browser tests drive the filtering that reads it

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
