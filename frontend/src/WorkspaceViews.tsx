import { useState } from 'react'
import {
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  AlertCircle,
  LayoutGrid,
  Plus,
  Star,
  Lock,
  Search,
  MoreHorizontal,
  Sparkles,
  Users,
  ArrowRight,
  Archive,
  Shield,
  CalendarDays,
} from 'lucide-react'
import type { Board, Card } from './types'
import { useWorkspace } from './context'
import { Avatar, Due, Empty, Field, dateTime, actionLabel } from './ui'

export function TaskRow({ card }: { card: Card }) {
  const { snapshot, openCard } = useWorkspace()
  const board = snapshot.boards.find((b) => b.id === card.board_id)
  return (
    <button className="task-row" onClick={() => openCard(card.id)}>
      <span className={'task-check ' + (card.status === 'DONE' ? 'done' : '')}>
        {card.status === 'DONE' && <CheckCircle2 size={17} />}
      </span>
      <span className="task-row-title">
        {card.title}
        <small>
          {board?.title} <span>·</span> AV-{card.number}
        </small>
      </span>
      <Due value={card.due_date} overdue={card.overdue} />
      <ArrowUpRight size={15} />
    </button>
  )
}
export function BoardCard({ board }: { board: Board }) {
  const { snapshot, navigate, perform } = useWorkspace()
  const cards = snapshot.cards.filter((c) => c.board_id === board.id && !c.inactive),
    done = cards.filter((c) => c.status === 'DONE').length
  const favorite = snapshot.favorites.includes(board.id)
  return (
    <article className={'board-card color-' + board.color}>
      <header>
        <span className={'board-symbol ' + board.color}>
          <LayoutGrid size={20} />
        </span>
        <button
          className={'icon-button ' + (favorite ? 'favorited' : '')}
          aria-label={favorite ? 'Unfavorite ' + board.title : 'Favorite ' + board.title}
          onClick={() => void perform({ action: 'favorite', board_id: board.id, value: !favorite })}
        >
          <Star size={17} fill={favorite ? 'currentColor' : 'none'} />
        </button>
      </header>
      <button className="board-card-title" onClick={() => navigate('board/' + board.id)}>
        {board.title}
        {board.visibility === 'private' && <Lock size={13} />}
      </button>
      <p>{board.description || 'Make space for your next great idea.'}</p>
      <div className="progress-caption">
        <span>{cards.length} tasks</span>
        <span>{cards.length ? Math.round((done / cards.length) * 100) : 0}% complete</span>
      </div>
      <div className="progress-track">
        <span style={{ width: (cards.length ? (done / cards.length) * 100 : 0) + '%' }} />
      </div>
      <footer>
        <span className="muted">
          {board.archived
            ? 'Archived board'
            : board.visibility === 'private'
              ? 'Private board'
              : 'Workspace board'}
        </span>
        <button
          aria-label={'Open ' + board.title}
          className="icon-button"
          onClick={() => navigate('board/' + board.id)}
        >
          <ArrowUpRight size={18} />
        </button>
      </footer>
    </article>
  )
}
export function Overview() {
  const { snapshot, user, navigate, openModal } = useWorkspace(),
    count = snapshot.counts
  const cards = snapshot.cards.filter((c) => !c.inactive),
    upcoming = cards
      .filter((c) => c.due_date && c.status !== 'DONE')
      .sort((a, b) => a.due_date!.localeCompare(b.due_date!))
      .slice(0, 5)
  const boards = snapshot.boards.filter((b) => !b.archived).slice(0, 3)
  const stats = [
    {
      name: 'Total tasks',
      value: count.tasks,
      icon: LayoutGrid,
      color: 'indigo',
      caption: 'Across your accessible boards',
    },
    {
      name: 'Completed',
      value: count.completed,
      icon: CheckCircle2,
      color: 'green',
      caption: 'Good work, well finished',
    },
    {
      name: 'In progress',
      value: count.in_progress,
      icon: Clock3,
      color: 'blue',
      caption: 'Moving in the right direction',
    },
    {
      name: 'Overdue',
      value: count.overdue,
      icon: AlertCircle,
      color: 'orange',
      caption: 'A little attention needed',
    },
  ]
  return (
    <div className="content-page overview">
      <div className="page-heading">
        <div>
          <div className="eyebrow">A LITTLE CLARITY FOR YOUR DAY</div>
          <h1>
            Good day, {user.name.split(' ')[0]} <span className="greeting-dot">✦</span>
          </h1>
          <p>Here's where things stand. Let's make room for what matters.</p>
        </div>
        {snapshot.role === 'OWNER' && (
          <button className="button primary" onClick={() => openModal({ kind: 'board' })}>
            <Plus size={16} />
            Create board
          </button>
        )}
      </div>
      {snapshot.workspace.is_demo && (
        <div className="sample-note">
          <Sparkles size={15} />
          <span>
            You're exploring the Acme Studio sample workspace. All numbers come from these sample records.
          </span>
        </div>
      )}
      <div className="stats-grid">
        {stats.map((s) => (
          <div className="stat-card" key={s.name}>
            <div>
              <span>{s.name}</span>
              <span className={'stat-icon ' + s.color}>
                <s.icon size={17} />
              </span>
            </div>
            <strong>{s.value}</strong>
            <p>{s.caption}</p>
          </div>
        ))}
      </div>
      <div className="section-title">
        <h2>
          Your boards <span className="count">{count.boards}</span>
        </h2>
        <button className="text-button" onClick={() => navigate('boards')}>
          View all boards <ArrowRight size={15} />
        </button>
      </div>
      {boards.length ? (
        <div className="boards-grid">
          {boards.map((b) => (
            <BoardCard key={b.id} board={b} />
          ))}
        </div>
      ) : (
        <Empty
          title="Your next chapter starts here"
          action={
            snapshot.role === 'OWNER' ? (
              <button className="button primary" onClick={() => openModal({ kind: 'board' })}>
                Create your first board
              </button>
            ) : undefined
          }
        >
          Boards give your team's ideas a place to move forward.
        </Empty>
      )}
      <div className="overview-bottom">
        <section className="panel deadlines">
          <div className="panel-heading">
            <h2>On the horizon</h2>
            <CalendarDays size={17} />
          </div>
          <p className="panel-intro">Upcoming deadlines and tasks that need attention.</p>
          {upcoming.length ? (
            upcoming.map((c) => <TaskRow key={c.id} card={c} />)
          ) : (
            <p className="inset muted">No upcoming deadlines. A little breathing room.</p>
          )}
          <footer>
            <button className="text-button" onClick={() => navigate('tasks')}>
              My tasks <span className="count">{count.assigned}</span>
              <ArrowRight size={14} />
            </button>
          </footer>
        </section>
        <section className="panel progress-panel">
          <div className="panel-heading">
            <h2>Making progress</h2>
            <span className="pill">Workspace snapshot</span>
          </div>
          <div className="progress-summary">
            <strong>
              {count.tasks ? Math.round((count.completed / count.tasks) * 100) : 0}
              <small>%</small>
            </strong>
            <span>
              of your tasks
              <br />
              are complete
            </span>
          </div>
          <div
            className="status-bar"
            role="img"
            aria-label={
              count.completed +
              ' completed, ' +
              count.in_progress +
              ' in progress, ' +
              (count.tasks - count.completed - count.in_progress) +
              ' to do'
            }
          >
            <i
              className="done"
              style={{ width: (count.tasks ? (count.completed / count.tasks) * 100 : 0) + '%' }}
            />
            <i
              className="doing"
              style={{ width: (count.tasks ? (count.in_progress / count.tasks) * 100 : 0) + '%' }}
            />
            <i className="todo" style={{ flex: 1 }} />
          </div>
          <div className="status-legend">
            <span>
              <i className="done" />
              Completed <b>{count.completed}</b>
            </span>
            <span>
              <i className="doing" />
              In progress <b>{count.in_progress}</b>
            </span>
            <span>
              <i className="todo" />
              To do <b>{count.tasks - count.completed - count.in_progress}</b>
            </span>
          </div>
          <div className="progress-foot">
            <span className="soft-icon">
              <Users size={19} />
            </span>
            <p>
              A shared effort.
              <br />
              <strong>
                {snapshot.members.length} active workspace{' '}
                {snapshot.members.length === 1 ? 'member' : 'members'}.
              </strong>
            </p>
          </div>
        </section>
      </div>
      <section className="panel" style={{ marginBottom: 24 }}>
        <div className="panel-heading">
          <h2>Deadline distribution</h2>
          <span className="muted small">Incomplete, active tasks</span>
        </div>
        <div className="deadline-distribution">
          {[
            { name: 'Overdue', value: cards.filter((c) => c.overdue).length },
            {
              name: 'Today',
              value: cards.filter((c) => c.status !== 'DONE' && c.due_date === snapshot.server_today).length,
            },
            {
              name: 'Next 6 days',
              value: cards.filter((c) => c.due_soon && c.due_date !== snapshot.server_today).length,
            },
            { name: 'No due date', value: cards.filter((c) => c.status !== 'DONE' && !c.due_date).length },
          ].map((d) => (
            <span key={d.name}>
              <b>{d.value}</b>
              {d.name}
              <meter
                min={0}
                max={Math.max(1, cards.length)}
                value={d.value}
                aria-label={d.name + ': ' + d.value + ' tasks'}
              />
            </span>
          ))}
        </div>
      </section>
      <section className="panel activity-panel">
        <div className="panel-heading">
          <h2>Recently in your workspace</h2>
          <button className="text-button" onClick={() => openModal({ kind: 'activity' })}>
            View activity <ArrowRight size={14} />
          </button>
        </div>
        {snapshot.activity.slice(0, 4).map((e) => (
          <div className="activity-row" key={e.id}>
            <Avatar name={e.actor_name} size="small" />
            <div>
              <strong>{e.actor_name}</strong> <span>{actionLabel(e.action)}</span>
              <small>{dateTime(e.created_at)}</small>
            </div>
          </div>
        ))}
        {!snapshot.activity.length && <p className="inset muted">Activity will appear as your team works.</p>}
      </section>
    </div>
  )
}
export function BoardsView({ favorites = false }: { favorites?: boolean }) {
  const { snapshot, openModal } = useWorkspace(),
    [query, setQuery] = useState(''),
    [archive, setArchive] = useState(false)
  const boards = snapshot.boards.filter(
    (b) =>
      b.archived === archive &&
      (!favorites || snapshot.favorites.includes(b.id)) &&
      b.title.toLowerCase().includes(query.toLowerCase())
  )
  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">A PLACE FOR EVERY PROJECT</div>
          <h1>{favorites ? 'Your favorites' : 'All boards'}</h1>
          <p>
            {favorites
              ? 'The work you like to keep close.'
              : 'Big ideas. Small steps. Everything in one place.'}
          </p>
        </div>
        {snapshot.role === 'OWNER' && (
          <button className="button primary" onClick={() => openModal({ kind: 'board' })}>
            <Plus size={16} />
            Create board
          </button>
        )}
      </div>
      <div className="list-toolbar">
        <label className="search-field">
          <Search size={17} />
          <input
            placeholder="Find a board…"
            aria-label="Find a board"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <button className={'button ' + (archive ? 'active' : '')} onClick={() => setArchive(!archive)}>
          <Archive size={16} />
          {archive ? 'Show active' : 'Archived boards'}
        </button>
      </div>
      {boards.length ? (
        <div className="boards-grid">
          {boards.map((b) => (
            <BoardCard key={b.id} board={b} />
          ))}
        </div>
      ) : (
        <Empty title={favorites ? 'Keep your important boards close' : 'No boards here yet'}>
          {favorites
            ? 'Star a board to find it here.'
            : 'Try a different search, or create a board to get started.'}
        </Empty>
      )}
    </div>
  )
}
export function TasksView() {
  const { snapshot, user } = useWorkspace(),
    [query, setQuery] = useState(''),
    [sort, setSort] = useState('due'),
    [board, setBoard] = useState('')
  const cards = snapshot.cards.filter(
    (c) =>
      !c.inactive &&
      c.assignee_id === user.id &&
      (!board || c.board_id === board) &&
      (c.title + ' ' + c.description).toLowerCase().includes(query.toLowerCase())
  )
  cards.sort((a, b) =>
    sort === 'title'
      ? a.title.localeCompare(b.title)
      : (a.due_date || '9999').localeCompare(b.due_date || '9999')
  )
  return (
    <div className="content-page tasks-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">FOCUS ON YOUR NEXT STEP</div>
          <h1>My tasks</h1>
          <p>Your work, with a little more perspective.</p>
        </div>
        <span className="pill">{cards.length} assigned tasks</span>
      </div>
      <div className="list-toolbar">
        <label className="search-field">
          <Search size={17} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your tasks…"
            aria-label="Search your tasks"
          />
        </label>
        <select aria-label="Task board filter" value={board} onChange={(e) => setBoard(e.target.value)}>
          <option value="">All boards</option>
          {snapshot.boards
            .filter((b) => !b.archived)
            .map((b) => (
              <option key={b.id} value={b.id}>
                {b.title}
              </option>
            ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort tasks">
          <option value="due">Due date</option>
          <option value="title">Title</option>
        </select>
      </div>
      {!cards.length ? (
        <Empty title="A clear to-do list">Tasks assigned to you will appear here.</Empty>
      ) : (
        ['Overdue', 'Today', 'This Week', 'Upcoming', 'No Due Date', 'Completed'].map((group) => {
          const items = cards.filter((c) => c.group === group)
          return items.length ? (
            <section className="task-group panel" key={group}>
              <div className="panel-heading">
                <h2>
                  {group} <span className="count">{items.length}</span>
                </h2>
              </div>
              {items.map((c) => (
                <TaskRow key={c.id} card={c} />
              ))}
            </section>
          ) : null
        })
      )}
    </div>
  )
}
export function MembersView() {
  const { snapshot, user, perform, openModal } = useWorkspace(),
    owner = snapshot.role === 'OWNER'
  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">GOOD WORK IS A TEAM EFFORT</div>
          <h1>People in your workspace</h1>
          <p>Give everyone the right place, and the right permissions.</p>
        </div>
        {owner && (
          <button className="button primary" onClick={() => openModal({ kind: 'invite' })}>
            <Plus size={16} />
            Invite member
          </button>
        )}
      </div>
      <section className="panel members-panel">
        <div className="panel-heading">
          <h2>
            Members <span className="count">{snapshot.members.length}</span>
          </h2>
          <Shield size={18} />
        </div>
        {snapshot.members.map((m) => (
          <div className="member-row" key={m.id}>
            <Avatar name={m.name} />
            <div className="member-identity">
              <strong>
                {m.name}
                {m.id === user.id && <small> (you)</small>}
              </strong>
              <span>{m.email}</span>
            </div>
            {owner && m.role !== 'OWNER' ? (
              <>
                <select
                  aria-label={'Role for ' + m.name}
                  value={m.role || 'MEMBER'}
                  onChange={(e) =>
                    void perform(
                      {
                        action: 'change_role',
                        workspace_id: snapshot.workspace.id,
                        user_id: m.id,
                        role: e.target.value as 'MEMBER' | 'VIEWER',
                      },
                      'Role updated'
                    )
                  }
                >
                  <option value="MEMBER">Member</option>
                  <option value="VIEWER">Viewer</option>
                </select>
                <button
                  className="button small"
                  onClick={() => {
                    if (confirm('Transfer ownership to ' + m.name + '? You will become a member.'))
                      void perform(
                        { action: 'transfer_owner', workspace_id: snapshot.workspace.id, user_id: m.id },
                        'Ownership transferred'
                      )
                  }}
                >
                  Make owner
                </button>
                <button
                  className="danger-link"
                  onClick={() => {
                    if (confirm('Remove ' + m.name + ' and unassign their tasks?'))
                      void perform(
                        { action: 'remove_member', workspace_id: snapshot.workspace.id, user_id: m.id },
                        'Member removed'
                      )
                  }}
                >
                  Remove
                </button>
              </>
            ) : (
              <span className="pill">{m.role?.toLowerCase()}</span>
            )}
          </div>
        ))}
      </section>
      {owner && (
        <section className="panel invitations">
          <div className="panel-heading">
            <h2>Invitations</h2>
          </div>
          {snapshot.invitations.length ? (
            snapshot.invitations.map((inv) => (
              <div className="member-row" key={inv.id}>
                <div className="member-identity">
                  <strong>{inv.email}</strong>
                  <span>
                    {inv.role.toLowerCase()} · {inv.status} · expires {dateTime(inv.expires_at)}
                  </span>
                  {inv.applicant_id && (
                    <span>
                      Authenticated account: <code>{inv.applicant_id}</code>. Verify this account with your
                      teammate before approving.
                    </span>
                  )}
                </div>
                {inv.status === 'awaiting-owner-approval' && (
                  <button
                    className="button primary small"
                    onClick={() =>
                      void perform(
                        {
                          action: 'approve_invite',
                          workspace_id: snapshot.workspace.id,
                          invitation_id: inv.id,
                        },
                        'Member approved'
                      )
                    }
                  >
                    Approve account
                  </button>
                )}
                {['pending', 'awaiting-owner-approval'].includes(inv.status) && (
                  <button
                    className="button small"
                    onClick={() =>
                      void perform(
                        {
                          action: 'revoke_invite',
                          workspace_id: snapshot.workspace.id,
                          invitation_id: inv.id,
                        },
                        'Invitation revoked'
                      )
                    }
                  >
                    Revoke
                  </button>
                )}
              </div>
            ))
          ) : (
            <p className="inset muted">No invitations yet. Invite a teammate when you're ready.</p>
          )}
        </section>
      )}
      <div className="permission-note">
        <Shield size={20} />
        <p>
          <strong>A clear boundary for every role.</strong>
          <br />
          Owners manage the workspace. Members organize work. Viewers can read accessible boards without
          changing them.
        </p>
      </div>
    </div>
  )
}
export function SettingsView() {
  const { snapshot, perform } = useWorkspace(),
    owner = snapshot.role === 'OWNER'
  const [version, setVersion] = useState(snapshot.workspace.version)
  return (
    <div className="content-page settings-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">MAKE THIS SPACE YOURS</div>
          <h1>Workspace settings</h1>
          <p>A few thoughtful defaults for the way your team works.</p>
        </div>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>General</h2>
        </div>
        {version !== snapshot.workspace.version && (
          <div className="conflict-note">
            Workspace settings changed.{' '}
            <button className="text-button" onClick={() => setVersion(snapshot.workspace.version)}>
              Reload current settings
            </button>
          </div>
        )}
        <form
          className="settings-form"
          key={version}
          onSubmit={async (e) => {
            e.preventDefault()
            const f = new FormData(e.currentTarget)
            const result = await perform<{ version: number }>(
              {
                action: 'update_workspace',
                workspace_id: snapshot.workspace.id,
                expected_version: version,
                name: String(f.get('name')),
                timezone: String(f.get('timezone')),
              },
              'Workspace updated'
            )
            if (result) setVersion(result.version)
          }}
        >
          <Field label="Workspace name">
            <input
              name="name"
              defaultValue={snapshot.workspace.name}
              required
              disabled={!owner}
              maxLength={80}
            />
          </Field>
          <Field label="Workspace timezone">
            <input
              name="timezone"
              list="timezones"
              defaultValue={snapshot.workspace.timezone}
              required
              disabled={!owner}
            />
            <datalist id="timezones">
              {[
                'UTC',
                'Asia/Karachi',
                'Asia/Dubai',
                'Europe/London',
                'Europe/Paris',
                'America/New_York',
                'America/Los_Angeles',
                'Asia/Singapore',
                'Australia/Sydney',
              ].map((z) => (
                <option key={z} value={z} />
              ))}
            </datalist>
          </Field>
          <p className="muted">
            Deadlines use calendar dates in this timezone. Changing it recalculates overdue indicators without
            changing due dates.
          </p>
          {owner && <button className="button primary">Save changes</button>}
        </form>
      </section>
      <section className="panel settings-info">
        <h2>Your connected workspace</h2>
        <p>Sign-in is managed by Dodil appid. Your team's data stays in this organization's DataK3 bucket.</p>
        <p>
          To connect an assistant, use <code>{location.origin}/mcp</code>. Sign in with your app account; the
          organization administrator may need to approve the connector once.
        </p>
        <a className="button" href="/.dodil/auth/logout">
          Sign out
        </a>
      </section>
    </div>
  )
}
