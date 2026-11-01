import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import {
  LayoutDashboard,
  CheckSquare,
  LayoutGrid,
  Star,
  Users,
  Settings,
  Search,
  Plus,
  ChevronDown,
  Sun,
  Moon,
  Monitor,
  Activity,
  Menu,
  X,
  ArrowRight,
  LogOut,
  Sparkles,
  RefreshCw,
} from 'lucide-react'
import { branding } from './branding'
import { api, command, ApiError } from './api'
import { WorkspaceContext, type ModalState } from './context'
import { Brand, Avatar, Dialog, Field, Loading, Empty, Due, Toast } from './ui'
import type { User, Workspace, Snapshot, Command, Card } from './types'
import { Overview, BoardsView, TasksView, MembersView, SettingsView } from './WorkspaceViews'
const BoardView = lazy(() => import('./BoardView'))
const CardDetails = lazy(() => import('./CardDetails'))
const ActionDialogs = lazy(() => import('./ActionDialogs'))

function WorkspaceForm({ onCreated, onClose }: { onCreated: (w: Workspace) => void; onClose?: () => void }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [demo, setDemo] = useState(false)
  const form = (
    <form
      onSubmit={async (e) => {
        e.preventDefault()
        setBusy(true)
        setError('')
        const f = new FormData(e.currentTarget)
        try {
          const result = await command<{ workspace_id: string }>({
            action: 'create_workspace',
            name: demo ? 'Acme Studio' : String(f.get('name')),
            timezone: String(f.get('timezone')),
            demo,
          })
          const list = await api<Workspace[]>('/workspaces')
          onCreated(list.find((w) => w.id === result.workspace_id)!)
        } catch (e) {
          setError((e as Error).message)
        } finally {
          setBusy(false)
        }
      }}
    >
      <Field label="Workspace name">
        <input
          name="name"
          placeholder="Your team or company"
          defaultValue=""
          disabled={demo}
          required={!demo}
          maxLength={80}
        />
      </Field>
      <Field label="Timezone">
        <input
          name="timezone"
          defaultValue={Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'}
          required
        />
      </Field>
      <label className="sample-option">
        <input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} />
        <span>
          <strong>Explore Acme Studio</strong>
          <small>
            Create a clearly marked sample workspace with three boards and real, editable sample tasks.
          </small>
        </span>
      </label>
      {error && (
        <p className="error-note" role="alert">
          {error}
        </p>
      )}
      <button className="button primary full" disabled={busy}>
        {busy ? 'Creating your workspace…' : 'Create workspace'}
        <ArrowRight size={16} />
      </button>
    </form>
  )
  return onClose ? (
    <Dialog title="Create workspace" onClose={onClose}>
      {form}
    </Dialog>
  ) : (
    <main className="welcome">
      <Brand />
      <div className="welcome-panel">
        <span className="eyebrow">A CLEARER WAY TO WORK TOGETHER</span>
        <h1>
          A little structure.
          <br />A lot of possibility.
        </h1>
        <p>Bring your projects, people, and next steps into one thoughtful workspace.</p>
        {form}
      </div>
      <small>Powered by Dodil · Your data, in your organization.</small>
    </main>
  )
}

export default function App() {
  const [user, setUser] = useState<User | null>(null),
    [spaces, setSpaces] = useState<Workspace[]>([]),
    [workspaceId, setWorkspaceId] = useState(''),
    [snapshot, setSnapshot] = useState<Snapshot | null>(null),
    [boot, setBoot] = useState(true),
    [error, setError] = useState(''),
    [unauth, setUnauth] = useState(false),
    [fixture, setFixture] = useState(false)
  const [route, setRoute] = useState(location.hash.slice(1) || 'overview'),
    [modal, setModal] = useState<ModalState | null>(null),
    [cardId, setCardId] = useState<string | null>(null),
    [createSpace, setCreateSpace] = useState(false),
    [menu, setMenu] = useState(false),
    [profile, setProfile] = useState(false),
    [theme, setTheme] = useState('system')
  const [toast, setToast] = useState<{ message: string; error: boolean } | null>(null),
    [search, setSearch] = useState(''),
    [searching, setSearching] = useState(false),
    [searchError, setSearchError] = useState(''),
    [results, setResults] = useState<Card[]>([]),
    [semantic, setSemantic] = useState(false),
    [indexStatus, setIndexStatus] = useState('')
  const requestRef = useRef(0),
    activeWorkspace = useRef(workspaceId),
    toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  activeWorkspace.current = workspaceId
  const notify = useCallback((message: string, isError = false) => {
    setToast({ message, error: isError })
    if (toastTimer.current) clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 7000)
  }, [])
  const navigate = useCallback((next: string) => {
    location.hash = next
    setMenu(false)
    setSearch('')
  }, [])
  useEffect(() => {
    const hash = () => setRoute(location.hash.slice(1) || 'overview')
    window.addEventListener('hashchange', hash)
    return () => window.removeEventListener('hashchange', hash)
  }, [])
  async function initialize() {
    setBoot(true)
    setError('')
    try {
      const [identity, list] = await Promise.all([
        api<{ user: User; theme: string; test_fixture?: boolean }>('/me'),
        api<Workspace[]>('/workspaces'),
      ])
      setUser(identity.user)
      setTheme(identity.theme)
      setFixture(!!identity.test_fixture)
      setSpaces(list)
      setWorkspaceId((current) => (list.some((w) => w.id === current) ? current : list[0]?.id || ''))
    } catch (e) {
      setUnauth(e instanceof ApiError && e.status === 401)
      setError((e as Error).message)
    } finally {
      setBoot(false)
    }
  }
  useEffect(() => {
    document.title = branding.name
    void initialize()
  }, [])
  const refresh = useCallback(async () => {
    const id = activeWorkspace.current
    if (!id) return
    const request = ++requestRef.current
    const next = await api<Snapshot>('/workspaces/' + id + '/snapshot')
    if (request === requestRef.current && id === activeWorkspace.current) setSnapshot(next)
  }, [])
  useEffect(() => {
    setSnapshot(null)
    setCardId(null)
    setModal(null)
    if (workspaceId)
      void refresh().catch((e) => {
        setError(e.message)
        notify(e.message, true)
      })
  }, [workspaceId, refresh, notify])
  useEffect(() => {
    const update = () => {
      if (document.visibilityState === 'visible' && !modal && !cardId && route !== 'settings')
        void refresh().catch((e) => notify(e.message, true))
    }
    const timer = setInterval(update, 30000)
    window.addEventListener('focus', update)
    return () => {
      clearInterval(timer)
      window.removeEventListener('focus', update)
    }
  }, [refresh, modal, cardId, route, notify])
  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      document.documentElement.dataset.theme = theme === 'system' ? (media.matches ? 'dark' : 'light') : theme
    }
    apply()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [theme])
  useEffect(() => {
    const event = (e: Event) => setModal({ kind: 'label', ...(e as CustomEvent).detail })
    window.addEventListener('avenboard:label', event)
    return () => window.removeEventListener('avenboard:label', event)
  }, [])
  async function perform<T = Record<string, unknown>>(body: Command, message?: string): Promise<T | null> {
    try {
      const result = await command<T>(body)
      try {
        await refresh()
      } catch {
        notify(
          'Saved successfully, but the view could not refresh. Refresh before making another change.',
          true
        )
        return result
      }
      if (message) notify(message)
      return result
    } catch (e) {
      notify((e as Error).message, true)
      try {
        await refresh()
      } catch {}
      return null
    }
  }
  useEffect(() => {
    if (!search.trim() || !workspaceId) {
      setResults([])
      setSearchError('')
      return
    }
    let valid = true
    const timer = setTimeout(async () => {
      setSearching(true)
      setSearchError('')
      try {
        const r = semantic
          ? await api<{ items: Card[]; indexing?: unknown }>('/semantic-search', {
              workspace_id: workspaceId,
              query: search,
            })
          : await api<{ items: Card[] }>(
              '/cards?workspace_id=' + workspaceId + '&query=' + encodeURIComponent(search)
            )
        if (valid) {
          setResults(r.items)
          setIndexStatus(semantic ? 'Semantic results exclude tasks still waiting to be indexed.' : '')
        }
      } catch (e) {
        if (valid) {
          setSearchError((e as Error).message)
          setResults([])
        }
      } finally {
        if (valid) setSearching(false)
      }
    }, 350)
    return () => {
      valid = false
      clearTimeout(timer)
    }
  }, [search, workspaceId, semantic])
  async function acceptInvitation() {
    try {
      const result = await command<{ status: string }>({ action: 'accept_invite', token: route.slice(7) })
      notify(
        result.status === 'active' || result.status === 'accepted'
          ? 'Invitation accepted'
          : 'Your acceptance is awaiting workspace owner approval.'
      )
      navigate('overview')
      await initialize()
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  function created(w: Workspace) {
    setSpaces((old) => [...old.filter((x) => x.id !== w.id), w])
    setWorkspaceId(w.id)
    setCreateSpace(false)
    navigate('overview')
  }
  if (boot) return <Loading />
  if (!user)
    return (
      <main className="welcome">
        <Brand />
        <div className="welcome-panel">
          <h1>{unauth ? 'Your workspace awaits.' : 'Unable to load your workspace'}</h1>
          <p role="alert">{error}</p>
          {unauth ? (
            <a className="button primary" href={'/.dodil/auth/login?return_to=' + encodeURIComponent('/')}>
              Sign in with Dodil
            </a>
          ) : (
            <button className="button primary" onClick={() => void initialize()}>
              Try again
            </button>
          )}
        </div>
      </main>
    )
  if (route.startsWith('invite/'))
    return (
      <main className="welcome">
        <Brand />
        <div className="welcome-panel">
          <h1>Join your team.</h1>
          <p>
            You're signed in as {user.email}. Accept this invitation to request access. The workspace owner
            may need to verify your account.
          </p>
          <button className="button primary" onClick={() => void acceptInvitation()}>
            Accept invitation
          </button>
          <button className="button" onClick={() => navigate('overview')}>
            Cancel
          </button>
        </div>
        {toast && <Toast {...toast} onClose={() => setToast(null)} />}
      </main>
    )
  if (!spaces.length) return <WorkspaceForm onCreated={created} />
  if (!snapshot)
    return (
      <div className="loading-page">
        {error ? (
          <>
            <p role="alert">{error}</p>
            <button className="button" onClick={() => void initialize()}>
              Reload workspaces
            </button>
          </>
        ) : (
          <Loading />
        )}
      </div>
    )
  const nav = [
    { route: 'overview', label: 'Overview', icon: LayoutDashboard },
    { route: 'tasks', label: 'My tasks', icon: CheckSquare },
    { route: 'boards', label: 'All boards', icon: LayoutGrid },
    { route: 'favorites', label: 'Favorites', icon: Star },
  ]
  const board = route.startsWith('board/') ? snapshot.boards.find((b) => b.id === route.slice(6)) : null
  const selected = cardId ? snapshot.cards.find((c) => c.id === cardId) : null
  const title =
    board?.title ||
    {
      overview: 'Overview',
      tasks: 'My tasks',
      boards: 'All boards',
      favorites: 'Favorites',
      members: 'Members',
      settings: 'Settings',
    }[route] ||
    'Workspace'
  return (
    <WorkspaceContext.Provider
      value={{
        snapshot,
        user,
        refresh,
        perform,
        setSnapshot,
        openCard: setCardId,
        openModal: setModal,
        navigate,
        notify,
      }}
    >
      <a
        className="skip-link"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault()
          document.getElementById('main-content')?.focus()
        }}
      >
        Skip to content
      </a>
      <div className="app-shell">
        {menu && (
          <button
            className="nav-backdrop"
            aria-label="Dismiss navigation backdrop"
            onClick={() => setMenu(false)}
          />
        )}
        <aside className={'sidebar ' + (menu ? 'open' : '')}>
          <div className="sidebar-brand">
            <Brand />
            <button
              className="icon-button mobile-only"
              aria-label="Close navigation"
              onClick={() => setMenu(false)}
            >
              <X size={19} />
            </button>
          </div>
          <div className="workspace-switch">
            <span className="workspace-monogram">{snapshot.workspace.name.slice(0, 1)}</span>
            <label>
              <span className="sr-only">Select workspace</span>
              <select
                value={workspaceId}
                onChange={(e) => {
                  setWorkspaceId(e.target.value)
                  navigate('overview')
                }}
              >
                {spaces.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
              <small>{snapshot.role.toLowerCase()} workspace</small>
            </label>
            <button
              className="icon-button compact"
              aria-label="Create workspace"
              onClick={() => setCreateSpace(true)}
            >
              <Plus size={15} />
            </button>
          </div>
          <div className="nav-caption">WORKSPACE</div>
          <nav aria-label="Main navigation">
            {nav.map((n) => (
              <button
                className={'nav-item ' + (route === n.route ? 'selected' : '')}
                key={n.route}
                aria-label={n.label}
                onClick={() => navigate(n.route)}
              >
                <n.icon size={18} />
                <span>{n.label}</span>
                {n.route === 'tasks' && snapshot.counts.assigned > 0 && (
                  <span className="nav-count">{snapshot.counts.assigned}</span>
                )}
              </button>
            ))}
          </nav>
          <div className="nav-caption">
            PINNED BOARDS <Star size={12} />
          </div>
          <nav aria-label="Favorite boards" className="pinned">
            {snapshot.boards
              .filter((b) => snapshot.favorites.includes(b.id) && !b.archived)
              .map((b) => (
                <button
                  key={b.id}
                  className={'nav-item ' + (board?.id === b.id ? 'selected' : '')}
                  onClick={() => navigate('board/' + b.id)}
                >
                  <span className={'board-dot ' + b.color} />
                  <span>{b.title}</span>
                </button>
              ))}
            {!snapshot.favorites.length && <p className="sidebar-hint">Star a board to keep it here.</p>}
          </nav>
          <div className="sidebar-bottom">
            <nav aria-label="Administration">
              <button
                className={'nav-item ' + (route === 'members' ? 'selected' : '')}
                onClick={() => navigate('members')}
              >
                <Users size={18} />
                Members
              </button>
              <button
                className={'nav-item ' + (route === 'settings' ? 'selected' : '')}
                onClick={() => navigate('settings')}
              >
                <Settings size={18} />
                Settings
              </button>
            </nav>
            <div className="theme-picker" aria-label="Appearance">
              {[
                { value: 'light', label: 'Light', icon: Sun },
                { value: 'dark', label: 'Dark', icon: Moon },
                { value: 'system', label: 'System', icon: Monitor },
              ].map((t) => (
                <button
                  key={t.value}
                  aria-label={t.label + ' theme'}
                  aria-pressed={theme === t.value}
                  className={theme === t.value ? 'selected' : ''}
                  onClick={async () => {
                    const previous = theme
                    setTheme(t.value)
                    const r = await perform({
                      action: 'preference',
                      theme: t.value as 'light' | 'dark' | 'system',
                    })
                    if (!r) setTheme(previous)
                  }}
                >
                  <t.icon size={14} />
                  {t.label}
                </button>
              ))}
            </div>
            <button className="profile-button" onClick={() => setProfile(!profile)} aria-expanded={profile}>
              <Avatar name={user.name} />
              <span>
                <strong>{user.name}</strong>
                <small>{user.email}</small>
              </span>
              <ChevronDown size={15} />
            </button>
            {profile && (
              <div className="profile-menu">
                <p>Signed in through Dodil appid</p>
                <a href="/.dodil/auth/logout">
                  <LogOut size={15} />
                  Sign out
                </a>
              </div>
            )}
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <button
              className="icon-button mobile-only"
              aria-label="Open navigation"
              onClick={() => setMenu(true)}
            >
              <Menu size={20} />
            </button>
            <div className="breadcrumb">
              <span>{snapshot.workspace.name}</span>
              <span>/</span>
              <strong>{title}</strong>
            </div>
            <div className="topbar-actions">
              <label className="global-search">
                <Search size={16} />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search tasks…"
                  aria-label="Search all tasks"
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') setSearch('')
                  }}
                />
              </label>
              <button
                className={
                  'icon-button activity-indicator ' + (snapshot.activity.length ? 'has-activity' : '')
                }
                aria-label={'View activity, ' + snapshot.activity.length + ' recent events'}
                onClick={() => setModal({ kind: 'activity' })}
              >
                <Activity size={19} />
              </button>
              <button
                className="icon-button"
                aria-label="Refresh workspace"
                onClick={() =>
                  void refresh()
                    .then(() => notify('Workspace refreshed'))
                    .catch((e) => notify(e.message, true))
                }
              >
                <RefreshCw size={17} />
              </button>
            </div>
          </header>
          {fixture && (
            <div className="fixture-banner">
              LOCAL QA PREVIEW · isolated in-memory fixtures · not connected to Dodil
            </div>
          )}
          {search.trim() && (
            <section className="search-results" aria-label="Search results">
              <header>
                <h3>Find your next step</h3>
                <label>
                  <input type="checkbox" checked={semantic} onChange={(e) => setSemantic(e.target.checked)} />
                  Semantic search
                </label>
                <button className="icon-button" aria-label="Close search" onClick={() => setSearch('')}>
                  <X size={17} />
                </button>
              </header>
              {searching ? (
                <Loading />
              ) : searchError ? (
                <p className="error-note" role="alert">
                  {searchError}
                  {semantic && (
                    <button className="text-button" onClick={() => setSemantic(false)}>
                      Use keyword search
                    </button>
                  )}
                </p>
              ) : results.length ? (
                results.map((c) => (
                  <button
                    className="search-result"
                    key={c.id}
                    onClick={() => {
                      setCardId(c.id)
                      setSearch('')
                    }}
                  >
                    <span>
                      <strong>{c.title}</strong>
                      <small>
                        AV-{c.number} · {snapshot.boards.find((b) => b.id === c.board_id)?.title}
                      </small>
                    </span>
                    <Due value={c.due_date} overdue={c.overdue} />
                  </button>
                ))
              ) : (
                <p className="muted">No matching tasks.</p>
              )}
              {indexStatus && semantic && <p className="small muted">{indexStatus}</p>}
              <p className="small muted">Showing at most 50 results. Narrow your search to find more.</p>
            </section>
          )}
          <main id="main-content" tabIndex={-1}>
            <Suspense fallback={<Loading />}>
              {board ? (
                <BoardView key={board.id} board={board} />
              ) : route === 'overview' ? (
                <Overview />
              ) : route === 'tasks' ? (
                <TasksView />
              ) : route === 'boards' ? (
                <BoardsView />
              ) : route === 'favorites' ? (
                <BoardsView favorites />
              ) : route === 'members' ? (
                <MembersView />
              ) : route === 'settings' ? (
                <SettingsView />
              ) : (
                <Empty
                  title="This page is unavailable"
                  action={
                    <button className="button" onClick={() => navigate('overview')}>
                      Go to overview
                    </button>
                  }
                >
                  It may have been removed or your access may have changed.
                </Empty>
              )}
            </Suspense>
            <footer className="app-footer">
              <span>{branding.tagline}</span>
              <span>Refreshes every 30 seconds and when you return.</span>
            </footer>
          </main>
        </div>
      </div>
      <Suspense fallback={<Loading />}>
        {selected && <CardDetails key={selected.id} card={selected} onClose={() => setCardId(null)} />}{' '}
        {modal && <ActionDialogs key={JSON.stringify(modal)} modal={modal} onClose={() => setModal(null)} />}
      </Suspense>
      {createSpace && <WorkspaceForm onCreated={created} onClose={() => setCreateSpace(false)} />}
      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </WorkspaceContext.Provider>
  )
}
