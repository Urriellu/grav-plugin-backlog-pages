<?php

declare(strict_types=1);

namespace Grav\Plugin;

use Grav\Common\Plugin;

/**
 * Backlog Pages: hierarchy and priority-by-person views over ordinary Grav pages.
 *
 * Epics are pages; stories are their children. Both are plain Markdown with
 * front matter, so they render, search, edit and version like every other page
 * on the site -- there is no database and no separate store.
 *
 * Two deliberate design choices:
 *
 * 1. **All data assembly happens here, not in Twig.** The templates get arrays
 *    that are already flattened, sorted and counted. Twig that has to sort by a
 *    nested header field is hard to write and harder to verify, and this plugin
 *    was written without any way to run Grav.
 *
 * 2. **A page opts in through its own front matter**, `<namespace>.view`, rather
 *    than through a template filename. With this plugin disabled the pages
 *    render as ordinary Grav pages showing their body text, so nothing 404s
 *    and nothing errors -- the views simply are not there.
 */
class BacklogPagesPlugin extends Plugin
{
    /** Statuses that mean an item needs nobody's attention. */
    private const CLOSED = ['done', 'cancelled'];

    /**
     * Everything a site might reasonably want to move, and what it is when
     * nobody has said otherwise.
     *
     * @var array<string,string>
     */
    private const DEFAULTS = [
        'backlog_route' => '/backlog',
        'roster_route' => '/team',
        'namespace' => 'backlog',
    ];

    /** @var array<string,string> */
    private const STATUS_LABELS = [
        'to-do' => 'To do',
        'in-progress' => 'In progress',
        'done' => 'Done',
        'cancelled' => 'Cancelled',
    ];

    public static function getSubscribedEvents(): array
    {
        return [
            'onPluginsInitialized' => ['onPluginsInitialized', 0],
        ];
    }

    public function onPluginsInitialized(): void
    {
        if ($this->isAdmin()) {
            return;
        }

        $this->enable([
            'onTwigTemplatePaths' => ['onTwigTemplatePaths', 0],
            'onPageInitialized' => ['onPageInitialized', 0],
            'onTwigSiteVariables' => ['onTwigSiteVariables', 0],
        ]);
    }

    public function onTwigTemplatePaths(): void
    {
        $this->grav['twig']->twig_paths[] = __DIR__ . '/templates';
    }

    /**
     * Point a page that declares a view at this plugin's template.
     *
     * Done on page initialisation rather than by filename so that the page
     * still renders as an ordinary page when this plugin is switched off.
     */
    public function onPageInitialized(): void
    {
        $page = $this->grav['page'] ?? null;
        if ($page === null) {
            return;
        }

        $view = $this->viewOf($page);
        if ($view !== null) {
            $page->template('backlog-' . $view);
        }
    }

    /**
     * Hand the current page's view, if it declares one, the data it needs.
     */
    public function onTwigSiteVariables(): void
    {
        $page = $this->grav['page'] ?? null;
        if ($page === null) {
            return;
        }

        $view = $this->viewOf($page);
        if ($view === null) {
            return;
        }

        $epics = $this->collectEpics();

        $twig = $this->grav['twig'];
        $twig->twig_vars['backlog_view'] = $view;
        $twig->twig_vars['backlog_epics'] = $epics;
        $twig->twig_vars['backlog_stories'] = $this->flatten($epics);
        $twig->twig_vars['backlog_labels'] = $this->labelsIn($epics);
        $twig->twig_vars['backlog_statuses'] = self::STATUS_LABELS;
        $twig->twig_vars['backlog_people'] = $this->collectPeople();
        $twig->twig_vars['backlog_namespace'] = $this->setting('namespace');
        $twig->twig_vars['backlog_roster_route'] = $this->setting('roster_route');
    }

    /**
     * The view a page asks for, or null when it asks for none.
     */
    private function viewOf($page): ?string
    {
        $view = $this->headerValue($page, 'view');

        return ($view === 'hierarchy' || $view === 'person') ? $view : null;
    }

    /**
     * Every epic under the configured backlog route, in rank order, each
     * carrying its stories.
     *
     * @return list<array<string,mixed>>
     */
    private function collectEpics(): array
    {
        $root = $this->grav['pages']->find($this->setting('backlog_route'));
        if ($root === null) {
            return [];
        }

        $epics = [];
        foreach ($root->children() as $child) {
            if ($this->headerValue($child, 'doc_type') !== 'epic') {
                continue;
            }

            $stories = [];
            foreach ($child->children() as $grandchild) {
                if ($this->headerValue($grandchild, 'doc_type') !== 'story') {
                    continue;
                }
                $stories[] = $this->item($grandchild);
            }
            $this->sortByRank($stories);

            $epic = $this->item($child);
            $epic['stories'] = $stories;
            $epic['total'] = count($stories);
            $epic['closed'] = count(array_filter(
                $stories,
                static fn (array $s): bool => in_array($s['status'], self::CLOSED, true)
            ));
            $epic['percent'] = $epic['total'] > 0
                ? (int) round(($epic['closed'] / $epic['total']) * 100)
                : 0;

            $epics[] = $epic;
        }

        $this->sortByRank($epics);

        return $epics;
    }

    /**
     * One epic or story, reduced to what a template needs.
     *
     * @return array<string,mixed>
     */
    private function item($page): array
    {
        $status = (string) ($this->headerValue($page, 'status') ?? '');

        return [
            'key' => (string) ($this->headerValue($page, 'key') ?? ''),
            'title' => (string) $page->title(),
            'route' => (string) $page->route(),
            'summary' => (string) ($page->header()->metadata['description'] ?? ''),
            'status' => $status,
            'status_label' => self::STATUS_LABELS[$status] ?? $status,
            'closed' => in_array($status, self::CLOSED, true),
            'rank' => (int) ($this->headerValue($page, 'rank') ?? PHP_INT_MAX),
            'owner' => (string) ($this->headerValue($page, 'owner') ?? ''),
            'labels' => $this->stringList($this->headerValue($page, 'labels')),
            'depends_on' => $this->stringList($this->headerValue($page, 'depends_on')),
            'traces_to' => $this->stringList($this->headerValue($page, 'traces_to')),
            'updated' => (string) ($this->headerValue($page, 'updated') ?? ''),
        ];
    }

    /**
     * Every story across every epic, in rank order.
     *
     * Ranks are global rather than per-epic, so this is the list that answers
     * "what is next" without reference to which epic something sits in.
     *
     * @param list<array<string,mixed>> $epics
     * @return list<array<string,mixed>>
     */
    private function flatten(array $epics): array
    {
        $stories = [];
        foreach ($epics as $epic) {
            foreach ($epic['stories'] as $story) {
                $story['epic_key'] = $epic['key'];
                $story['epic_title'] = $epic['title'];
                $story['epic_route'] = $epic['route'];
                $stories[] = $story;
            }
        }
        $this->sortByRank($stories);

        return $stories;
    }

    /**
     * @param list<array<string,mixed>> $epics
     * @return list<string>
     */
    private function labelsIn(array $epics): array
    {
        $labels = [];
        foreach ($epics as $epic) {
            foreach ($epic['stories'] as $story) {
                foreach ($story['labels'] as $label) {
                    $labels[$label] = true;
                }
            }
        }
        $labels = array_keys($labels);
        sort($labels);

        return $labels;
    }

    /**
     * The roster from the team page's front matter.
     *
     * Capability, not assignment: `can_pick` says what somebody is able to take
     * on, which is the question the person view answers.
     *
     * @return list<array<string,mixed>>
     */
    private function collectPeople(): array
    {
        $team = $this->grav['pages']->find($this->setting('roster_route'));
        if ($team === null) {
            return [];
        }

        $people = $this->headerValue($team, 'people');
        if (!is_array($people)) {
            return [];
        }

        $out = [];
        foreach ($people as $person) {
            if (!is_array($person) || empty($person['id'])) {
                continue;
            }
            $out[] = [
                'id' => (string) $person['id'],
                'name' => (string) ($person['name'] ?? $person['id']),
                'role' => (string) ($person['role'] ?? ''),
                'can_pick' => $this->stringList($person['can_pick'] ?? []),
            ];
        }

        return $out;
    }

    /**
     * A configured value, falling back to this plugin's own default.
     */
    private function setting(string $key): string
    {
        $value = $this->grav['config']->get('plugins.backlog-pages.' . $key);

        return is_string($value) && $value !== '' ? $value : self::DEFAULTS[$key];
    }

    /**
     * Read a key out of a page's front-matter namespace block.
     *
     * The namespace is configurable because a site that already has its own
     * front-matter conventions should not have to adopt somebody else's.
     */
    private function headerValue($page, string $key)
    {
        $namespace = $this->setting('namespace');
        $header = $page->header();
        if (!isset($header->{$namespace}) || !is_array($header->{$namespace})) {
            return null;
        }

        return $header->{$namespace}[$key] ?? null;
    }

    /**
     * @return list<string>
     */
    private function stringList($value): array
    {
        if ($value === null || $value === '') {
            return [];
        }
        if (!is_array($value)) {
            $value = [$value];
        }

        return array_values(array_map(static fn ($v): string => (string) $v, $value));
    }

    /**
     * @param list<array<string,mixed>> $items
     */
    private function sortByRank(array &$items): void
    {
        usort(
            $items,
            static fn (array $a, array $b): int => $a['rank'] <=> $b['rank'] ?: strcmp($a['key'], $b['key'])
        );
    }
}
