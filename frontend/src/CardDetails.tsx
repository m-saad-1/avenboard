import { useEffect, useState } from 'react'
import {
  AlignLeft,
  CalendarDays,
  Tag,
  UserRound,
  CheckSquare,
  Plus,
  Sparkles,
  GitBranch,
  History,
  Archive,
  Trash2,
  ArrowUp,
  ArrowDown,
  LoaderCircle,
} from 'lucide-react'
import { useWorkspace, eligibleMembers } from './context'
import { api } from './api'
import { Dialog, Field, Avatar, dateTime, actionLabel } from './ui'
import type { Card, Command, Activity } from './types'
export default function CardDetails({ card, onClose }: { card: Card; onClose: () => void }) {
  const { snapshot, perform, notify, setSnapshot } = useWorkspace()
  const [version, setVersion] = useState(card.version),
    [name, setName] = useState(card.title),
    [description, setDescription] = useState(card.description),
    [due, setDue] = useState(card.due_date || ''),
    [assignee, setAssignee] = useState(card.assignee_id || '')
  const [editingItem, setEditingItem] = useState<string | null>(null),
    [itemText, setItemText] = useState(''),
    [events, setEvents] = useState<Activity[]>([]),
    [eventTotal, setEventTotal] = useState(0),
    [item, setItem] = useState(''),
    [dependency, setDependency] = useState(''),
    [busy, setBusy] = useState(false),
    [generated, setGenerated] = useState<string[] | null>(null)
  const board = snapshot.boards.find((b) => b.id === card.board_id)!,
    lanes = snapshot.lists.filter((l) => l.board_id === card.board_id && !l.archived),
    canEdit = snapshot.role !== 'VIEWER' && !card.inactive
  const labels = snapshot.labels.filter((l) => l.board_id === card.board_id),
    members = eligibleMembers(snapshot, card.board_id)
  const edges = snapshot.dependencies.filter((d) => d.card_id === card.id),
    reverse = snapshot.dependencies.filter((d) => d.prerequisite_id === card.id)
  async function loadEvents(offset = 0) {
    try {
      const r = await api<{ items: Activity[]; total: number }>(
        '/cards/' + card.id + '/activity?offset=' + offset
      )
      setEvents((old) => (offset ? [...old, ...r.items] : r.items))
      setEventTotal(r.total)
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  useEffect(() => {
    void loadEvents()
  }, [card.id, card.version])
  async function mutate(cmd: Command, message?: string) {
    setBusy(true)
    const r = await perform<Card>(cmd, message)
    setBusy(false)
    if (r) setVersion(r.version)
    return r
  }
  async function aiChecklist() {
    setBusy(true)
    try {
      const r = await api<{ items: string[]; expected_version: number }>(
        '/cards/' + card.id + '/generate-checklist',
        {}
      )
      if (r.expected_version !== version) {
        notify('The card changed. Reload its latest version before generating.', true)
        return
      }
      setGenerated(r.items)
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  function reload() {
    setName(card.title)
    setDescription(card.description)
    setDue(card.due_date || '')
    setAssignee(card.assignee_id || '')
    setVersion(card.version)
    setGenerated(null)
  }
  async function move(position: number, listId = card.list_id) {
    await mutate(
      { action: 'move_card', card_id: card.id, expected_version: version, list_id: listId, position },
      'Task moved'
    )
  }
  return (
    <Dialog title={'AV-' + card.number + ' · ' + board.title} onClose={onClose} wide>
      <div className="card-detail">
        <div className="detail-kicker">
          <span className={'status-dot ' + card.status} />
          {snapshot.lists.find((l) => l.id === card.list_id)?.title}
          <span className="pill">
            {card.status === 'DONE' ? 'Completed' : card.overdue ? 'Overdue' : 'Active task'}
          </span>
        </div>
        {version !== card.version && (
          <div className="conflict-note">
            This task changed while you were viewing it.{' '}
            <button className="text-button" onClick={reload}>
              Reload latest
            </button>
          </div>
        )}
        <form
          onSubmit={async (e) => {
            e.preventDefault()
            await mutate(
              {
                action: 'update_card',
                card_id: card.id,
                expected_version: version,
                changes: { title: name, description, due_date: due || null, assignee_id: assignee || null },
              },
              'Task saved'
            )
          }}
        >
          <label className="detail-title">
            <span className="sr-only">Task title</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!canEdit || busy}
              maxLength={160}
              required
            />
          </label>
          <div className="detail-fields">
            <Field label="Status / list">
              <select
                value={card.list_id}
                disabled={!canEdit || busy}
                onChange={(e) => void move(0, e.target.value)}
              >
                {lanes.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.title}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Assignee">
              <select
                value={assignee}
                disabled={!canEdit || busy}
                onChange={(e) => setAssignee(e.target.value)}
              >
                <option value="">Unassigned</option>
                {members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Due date">
              <input
                type="date"
                value={due}
                disabled={!canEdit || busy}
                onChange={(e) => setDue(e.target.value)}
              />
            </Field>
          </div>
          <section className="detail-section">
            <h3>
              <AlignLeft size={16} />
              Description
            </h3>
            <textarea
              aria-label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={!canEdit || busy}
              rows={5}
              maxLength={20000}
              placeholder="Add context, a clear outcome, or a useful link…"
            />
          </section>
          {canEdit && (
            <div className="save-row">
              <span className="muted">Your changes are saved when you choose Save.</span>
              <button className="button primary small" disabled={busy}>
                Save task
              </button>
            </div>
          )}
        </form>
        <section className="detail-section">
          <h3>
            <Tag size={16} />
            Labels
          </h3>
          <div className="chips label-picker">
            {labels.map((label) => (
              <button
                disabled={!canEdit || busy}
                key={label.id}
                className={'chip ' + label.color + (card.label_ids.includes(label.id) ? ' picked' : '')}
                aria-pressed={card.label_ids.includes(label.id)}
                onClick={() =>
                  void mutate({
                    action: 'update_card',
                    card_id: card.id,
                    expected_version: version,
                    changes: {
                      label_ids: card.label_ids.includes(label.id)
                        ? card.label_ids.filter((id) => id !== label.id)
                        : [...card.label_ids, label.id],
                    },
                  })
                }
              >
                {label.name}
                {card.label_ids.includes(label.id) && <span> ✓</span>}
              </button>
            ))}
            {!labels.length && (
              <p className="muted">No labels on this board. Add one in the board settings.</p>
            )}
          </div>
        </section>
        <section className="detail-section">
          <div className="section-title">
            <h3>
              <CheckSquare size={16} />
              Checklist{' '}
              <span className="count">
                {card.checklist.filter((i) => i.completed).length}/{card.checklist.length}
              </span>
            </h3>
            <button
              className="button small"
              disabled={busy || card.inactive}
              onClick={() => void aiChecklist()}
            >
              {busy ? <LoaderCircle size={14} className="spin" /> : <Sparkles size={14} />}Generate with AI
            </button>
          </div>
          {card.checklist.map((i) => (
            <div className="checklist-row" key={i.id}>
              <label>
                <input
                  type="checkbox"
                  checked={i.completed}
                  disabled={!canEdit || busy}
                  onChange={() => {
                    const next = card.checklist.map((x) => ({
                      ...x,
                      completed: x.id === i.id ? !x.completed : x.completed,
                    }))
                    setSnapshot((previous) =>
                      previous
                        ? {
                            ...previous,
                            cards: previous.cards.map((c) =>
                              c.id === card.id ? { ...c, checklist: next } : c
                            ),
                          }
                        : previous
                    )
                    void mutate({
                      action: 'save_checklist',
                      card_id: card.id,
                      expected_version: version,
                      mode: 'replace',
                      items: next.map((x) => ({ id: x.id, title: x.title, completed: x.completed })),
                    })
                  }}
                />
                <span className={i.completed ? 'struck' : ''}>{i.title}</span>
              </label>
              {canEdit && (
                <>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => {
                      setEditingItem(i.id)
                      setItemText(i.title)
                    }}
                    aria-label={'Edit checklist item ' + i.title}
                  >
                    Edit
                  </button>
                  <button
                    className="icon-button compact"
                    disabled={busy || card.checklist[0].id === i.id}
                    aria-label={'Move checklist item up ' + i.title}
                    onClick={() => {
                      const list = [...card.checklist],
                        index = list.findIndex((x) => x.id === i.id)
                      ;[list[index - 1], list[index]] = [list[index], list[index - 1]]
                      void mutate({
                        action: 'save_checklist',
                        card_id: card.id,
                        expected_version: version,
                        mode: 'replace',
                        items: list.map((x) => ({ id: x.id, title: x.title, completed: x.completed })),
                      })
                    }}
                  >
                    <ArrowUp size={13} />
                  </button>
                  <button
                    className="icon-button compact"
                    aria-label={'Remove checklist item ' + i.title}
                    disabled={busy}
                    onClick={() =>
                      void mutate({
                        action: 'save_checklist',
                        card_id: card.id,
                        expected_version: version,
                        mode: 'replace',
                        items: card.checklist
                          .filter((x) => x.id !== i.id)
                          .map((x) => ({ id: x.id, title: x.title, completed: x.completed })),
                      })
                    }
                  >
                    <Trash2 size={13} />
                  </button>
                </>
              )}
            </div>
          ))}
          {editingItem && (
            <form
              className="inline-form"
              onSubmit={async (e) => {
                e.preventDefault()
                const r = await mutate({
                  action: 'save_checklist',
                  card_id: card.id,
                  expected_version: version,
                  mode: 'replace',
                  items: card.checklist.map((x) => ({
                    id: x.id,
                    title: x.id === editingItem ? itemText : x.title,
                    completed: x.completed,
                  })),
                })
                if (r) setEditingItem(null)
              }}
            >
              <input
                aria-label="Edit checklist text"
                value={itemText}
                onChange={(e) => setItemText(e.target.value)}
                required
                maxLength={300}
              />
              <button className="button small" disabled={busy}>
                Save item
              </button>
              <button className="button small" type="button" onClick={() => setEditingItem(null)}>
                Cancel
              </button>
            </form>
          )}
          {canEdit && (
            <form
              className="inline-form"
              onSubmit={async (e) => {
                e.preventDefault()
                const r = await mutate({
                  action: 'save_checklist',
                  card_id: card.id,
                  expected_version: version,
                  items: [{ title: item }],
                })
                if (r) setItem('')
              }}
            >
              <input
                value={item}
                onChange={(e) => setItem(e.target.value)}
                placeholder="Add a checklist item…"
                aria-label="Checklist item"
                required
                maxLength={300}
              />
              <button className="button small" disabled={busy}>
                <Plus size={15} />
                Add
              </button>
            </form>
          )}
          {generated && (
            <div className="ai-preview">
              <h4>
                <Sparkles size={15} />
                AI suggestion · not saved
              </h4>
              <p>Review and edit these steps before adding them.</p>
              {generated.map((value, index) => (
                <input
                  key={index}
                  aria-label={'Suggested checklist item ' + (index + 1)}
                  value={value}
                  maxLength={300}
                  onChange={(e) => setGenerated(generated.map((v, i) => (i === index ? e.target.value : v)))}
                />
              ))}
              <div className="dialog-actions">
                <button className="button small" onClick={() => setGenerated(null)}>
                  Discard
                </button>
                {canEdit && (
                  <button
                    className="button primary small"
                    disabled={busy || generated.some((x) => !x.trim())}
                    onClick={async () => {
                      const r = await mutate(
                        {
                          action: 'save_checklist',
                          card_id: card.id,
                          expected_version: version,
                          items: generated.map((t) => ({ title: t })),
                          mode: 'append',
                        },
                        'Checklist added'
                      )
                      if (r) setGenerated(null)
                    }}
                  >
                    Save reviewed checklist
                  </button>
                )}
              </div>
            </div>
          )}
        </section>
        <section className="detail-section">
          <h3>
            <GitBranch size={16} />
            Dependencies
          </h3>
          <p className="muted">Blocked by</p>
          {edges.map((edge) => {
            const other = snapshot.cards.find((c) => c.id === edge.prerequisite_id)
            return (
              <div className="dependency-row" key={edge.id}>
                <span className={'status-dot ' + (other?.status || 'TODO')} />
                <span>
                  {other?.title || 'Deleted prerequisite'}
                  {(!other || other.inactive) && <small className="overdue"> · Unresolved</small>}
                </span>
                {canEdit && (
                  <button
                    className="icon-button"
                    aria-label="Remove dependency"
                    disabled={busy}
                    onClick={() =>
                      void mutate({
                        action: 'remove_dependency',
                        card_id: card.id,
                        expected_version: version,
                        prerequisite_id: edge.prerequisite_id,
                      })
                    }
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            )
          })}
          {!edges.length && <p className="small muted">No blockers linked.</p>}
          {canEdit && (
            <form
              className="inline-form"
              onSubmit={async (e) => {
                e.preventDefault()
                const r = await mutate(
                  {
                    action: 'add_dependency',
                    card_id: card.id,
                    expected_version: version,
                    prerequisite_id: dependency,
                  },
                  'Dependency linked'
                )
                if (r) setDependency('')
              }}
            >
              <select
                required
                aria-label="Prerequisite task"
                value={dependency}
                onChange={(e) => setDependency(e.target.value)}
              >
                <option value="">Link a prerequisite…</option>
                {snapshot.cards
                  .filter(
                    (c) =>
                      c.board_id === card.board_id &&
                      c.id !== card.id &&
                      !c.inactive &&
                      !edges.some((e) => e.prerequisite_id === c.id)
                  )
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      AV-{c.number} · {c.title}
                    </option>
                  ))}
              </select>
              <button className="button small" disabled={busy || !dependency}>
                Link
              </button>
            </form>
          )}
          {reverse.length > 0 && (
            <div className="blocking">
              <p className="muted">Blocking</p>
              {reverse.map((edge) => (
                <p key={edge.id}>
                  ↳ {snapshot.cards.find((c) => c.id === edge.card_id)?.title || 'Deleted task'}
                </p>
              ))}
            </div>
          )}
        </section>
        <section className="detail-section">
          <h3>
            <History size={16} />
            Activity
          </h3>
          <div className="timeline">
            {events.map((e) => (
              <div className="timeline-item" key={e.id}>
                <Avatar name={e.actor_name} size="small" />
                <div>
                  <p>
                    <strong>{e.actor_name}</strong> {actionLabel(e.action)}
                  </p>
                  <time>{dateTime(e.created_at)}</time>
                  {e.action.endsWith('_changed') && (
                    <details>
                      <summary>View change</summary>
                      <div className="change-values">
                        <pre>{e.before_json}</pre>
                        <span>→</span>
                        <pre>{e.after_json}</pre>
                      </div>
                    </details>
                  )}
                </div>
              </div>
            ))}
          </div>
          {events.length < eventTotal && (
            <button className="button small" onClick={() => void loadEvents(events.length)}>
              Load more activity
            </button>
          )}
        </section>
        <div className="detail-footer">
          <p className="small muted">
            Created {dateTime(card.created_at)}
            <br />
            Last updated {dateTime(card.updated_at)}
          </p>
          {canEdit && (
            <div className="detail-tools">
              <button
                className="button small"
                disabled={busy}
                onClick={() => void move(Math.max(0, card.position - 1))}
              >
                <ArrowUp size={14} />
                Move up
              </button>
              <button className="button small" disabled={busy} onClick={() => void move(card.position + 1)}>
                <ArrowDown size={14} />
                Move down
              </button>
              <button
                className="button small"
                disabled={busy}
                onClick={async () => {
                  if (confirm('Archive this task?')) {
                    const r = await mutate(
                      { action: 'archive_card', card_id: card.id, expected_version: version },
                      'Task archived'
                    )
                    if (r) onClose()
                  }
                }}
              >
                <Archive size={14} />
                Archive
              </button>
              <button
                className="icon-button danger"
                aria-label="Delete task"
                disabled={busy}
                onClick={async () => {
                  if (
                    confirm(
                      'Delete this task? It will disappear from active work; its audit history is retained.'
                    )
                  ) {
                    const r = await mutate(
                      { action: 'delete_card', card_id: card.id, expected_version: version },
                      'Task deleted'
                    )
                    if (r) onClose()
                  }
                }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
    </Dialog>
  )
}
