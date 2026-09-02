# Backlog Pages — a Grav plugin

Hierarchy and priority-by-person views over a backlog held as **ordinary Grav
pages**.

Epics are pages; stories are their children. Both are plain Markdown with front
matter, so they render, search, edit and version like every other page on the
site. There is no database, no separate store and nothing to keep in sync.

Two views:

- **Hierarchy** — every epic with its stories, collapsible, filterable by
  status and label, searchable, ordered by rank. Closed items are hidden until
  asked for.
- **Priority by person** — pick anybody and see the open stories they could
  pick up, in rank order, filtered to the labels they are able to work on.
  Capability, not assignment: the question is *what could this person do next*.

Filtering runs in the browser over markup that is already complete, so with
JavaScript off both pages still show everything — they simply stop filtering.
No framework, and nothing loaded from a CDN.

## Requirements

- Grav 1.7 or 2.0
- PHP 7.4 or later

There is nothing to build and no dependency beyond Grav itself.

## Installing

### From the Grav Package Manager

```bash
bin/gpm install backlog-pages
```

Or, in the Grav admin panel, **Plugins → Add** and search for *Backlog Pages*.

### Manually

Download the [latest release](https://github.com/Urriellu/grav-plugin-backlog-pages/releases)
and unpack it into `user/plugins/`, or clone it:

```bash
cd /path/to/grav/user/plugins
git clone https://github.com/Urriellu/grav-plugin-backlog-pages backlog-pages
```

The target directory must be **`backlog-pages`**. Grav takes the plugin's slug
from the directory name, and it has to match `backlog-pages.php` and
`backlog-pages.yaml` inside. The repository itself is called
`grav-plugin-backlog-pages` because that is Grav's convention for a plugin
*repository* — the two names differ on purpose, and only the directory name
matters to Grav.

## The front-matter contract

### An epic

```yaml
---
title: 'Decide the product shape'
backlog:
    doc_type: epic
    key: E-01
    rank: 10
    status: to-do          # to-do | in-progress | done | cancelled
    labels: [research]
---
```

### A story — a child page of an epic

```yaml
---
title: 'Compare sensing modalities'
backlog:
    doc_type: story
    key: S-002
    rank: 20               # global, not per-epic — see below
    status: to-do
    owner: alex
    labels: [research, hardware]
    depends_on: [S-001]
    traces_to: [ADR-0006]  # optional, free-form; shown as a tag
---
```

### A view page

```yaml
---
title: Hierarchy
backlog:
    view: hierarchy        # or: person
---
```

A page opts in through its own front matter rather than through a template
filename. **With the plugin disabled those pages render as ordinary Grav
pages** showing their body text — nothing 404s and nothing errors, which makes
the plugin safe to switch off if it misbehaves.

### The roster

The person view reads its people from the front matter of one page:

```yaml
---
title: Team
backlog:
    people:
        -   id: alex
            name: Alex
            role: 'Engineering'
            can_pick: [software, hardware]
        -   id: sam
            name: Sam
            can_pick: [research]
---
```

`can_pick` is a list of labels. A story appears for somebody when it carries at
least one label they can pick up.

## Ranks are global

`rank` is an integer ordering **every story on the site**, not the stories
within an epic. One ordered list then answers "what is next", and the order
inside an epic falls out of it for free. There are no priority levels — no
high, medium or low — because a rank that is total says more than a bucket that
is not.

Nothing enforces uniqueness; that is the site's business. If two stories share
a rank they are ordered by key, deterministically but arbitrarily.

## Configuration

`user/config/plugins/backlog-pages.yaml`:

| Setting | Default | What it does |
| --- | --- | --- |
| `enabled` | `true` | |
| `backlog_route` | `/backlog` | The page whose children are the epics |
| `roster_route` | `/team` | The page whose front matter lists the people |
| `namespace` | `backlog` | The front-matter key the plugin reads its fields from |
| `hide_closed_by_default` | `true` | Hide Done and Cancelled until the toggle is used |

`namespace` exists so that a site with its own front-matter conventions does
not have to adopt somebody else's. Set it to whatever the site already uses.

## Theme compatibility

The plugin never touches the theme. It registers its templates through
`onTwigTemplatePaths` and switches a page's template on `onPageInitialized`, so
it works with any theme providing a `content` block — which is every Grav theme
that follows the convention, Quark included.

Its styles are scoped to `.backlog-*` classes and use `rgba(128,128,128,…)`
borders rather than fixed colours, so they sit acceptably on a light or dark
theme without being told which.

## Status

**Early.** Written for one site and generalised afterwards. The front-matter
contract is stable enough to build on; the templates are likely to change.

Issues and pull requests welcome.

## Licence

MIT. See [LICENSE](LICENSE).
