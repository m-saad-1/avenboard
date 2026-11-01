import { useEffect, useState } from 'react'
import { Sparkles, Copy, Plus, Trash2 } from 'lucide-react'
import { useWorkspace, eligibleMembers, type ModalState } from './context'
import { Dialog, Field, palette, dateTime, Avatar, actionLabel, Loading } from './ui'
import { api } from './api'
import type { Board, Command, Activity } from './types'

export default function ActionDialogs({ modal, onClose }: { modal: ModalState; onClose: () => void }) {
  const { snapshot, perform, notify, navigate, openCard, openModal } = useWorkspace()
  const board = snapshot.boards.find((b) => b.id === modal.boardId)
  const label = snapshot.labels.find((l) => l.id === modal.labelId)
  const [busy, setBusy] = useState(false),
    [link, setLink] = useState(''),
    [ai, setAi] = useState<{
      suggestions: string
      as_of: string
      facts: { total: number; completed: number; overdue: number }
    } | null>(null),
    [error, setError] = useState('')
  const [events, setEvents] = useState<Activity[]>([]),
    [total, setTotal] = useState(0)
  async function loadActivity(offset = 0) {
    try {
      const r = await api<{ items: Activity[]; total: number }>(
        '/workspaces/' +
          snapshot.workspace.id +
          '/activity?offset=' +
          offset +
          (board ? '&board_id=' + board.id : '')
      )
      setEvents((prev) => (offset ? [...prev, ...r.items] : r.items))
      setTotal(r.total)
    } catch (e) {
      setError((e as Error).message)
    }
  }
  async function loadAI() {
    if (!board) return
    setBusy(true)
    setError('')
    try {
      setAi(
        await api(
          '/boards/' + board.id + '/' + (modal.aiKind === 'recommendations' ? 'recommendations' : 'summary'),
          {}
        )
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  useEffect(() => {
    if (modal.kind === 'ai') void loadAI()
    if (modal.kind === 'activity') void loadActivity()
  }, [])
  const titles = {
    dependencies: 'Dependency map',
    board: 'Create a board',
    list: 'Add a list',
    card: 'Create a task',
    'board-settings': 'Board settings',
    label: label ? 'Edit label' : 'Board labels',
    invite: 'Invite a teammate',
    activity: 'Workspace activity',
    ai: modal.aiKind === 'recommendations' ? 'Suggested next steps' : 'Board summary',
  }
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setBusy(true)
    const f = new FormData(e.currentTarget),
      get = (key: string) => String(f.get(key) || '')
    let cmd: Command
    switch (modal.kind) {
      case 'board':
        cmd = {
          action: 'create_board',
          workspace_id: snapshot.workspace.id,
          title: get('title'),
          description: get('description'),
          visibility: get('visibility') as Board['visibility'],
          color: get('color'),
        }
        break
      case 'list':
        cmd = {
          action: 'create_list',
          board_id: board!.id,
          title: get('title'),
          category: get('category') as 'TODO' | 'IN_PROGRESS' | 'DONE',
        }
        break
      case 'card':
        cmd = {
          action: 'create_card',
          list_id: get('list'),
          title: get('title'),
          description: get('description'),
          assignee_id: get('assignee') || null,
          due_date: get('due') || null,
          label_ids: f.getAll('labels').map(String),
        }
        break
      case 'board-settings':
        cmd = {
          action: 'update_board',
          board_id: board!.id,
          expected_version: board!.version,
          changes: {
            title: get('title'),
            description: get('description'),
            visibility: get('visibility') as Board['visibility'],
            color: get('color'),
          },
        }
        break
      case 'label':
        cmd = {
          action: 'save_label',
          board_id: board!.id,
          label_id: label?.id,
          name: get('name'),
          color: get('color'),
          description: get('description'),
        }
        break
      case 'invite':
        cmd = {
          action: 'invite_member',
          workspace_id: snapshot.workspace.id,
          email: get('email'),
          role: get('role') as 'MEMBER' | 'VIEWER',
        }
        break
      default:
        setBusy(false)
        return
    }
    const result = await perform<{ id?: string; token?: string }>(cmd, 'Saved')
    setBusy(false)
    if (result) {
      if (result.token) setLink(location.origin + '/#invite/' + result.token)
      else {
        onClose()
        if (modal.kind === 'board' && result.id) navigate('board/' + result.id)
      }
    }
  }
  const colors = (
    <Field label="Color">
      <select name="color" defaultValue={label?.color || board?.color || 'indigo'}>
        {palette.map((c) => (
          <option key={c}>{c}</option>
        ))}
      </select>
    </Field>
  )
  return (
    <Dialog title={titles[modal.kind]} onClose={onClose}>
      {modal.kind === 'ai' ? (
        <div className="ai-content">
          {busy && <Loading />}
          {error && (
            <div className="error-note">
              <p>{error}</p>
              <button className="button" onClick={() => void loadAI()}>
                Try again
              </button>
            </div>
          )}
          {ai && (
            <>
              <p className="eyebrow">DATABASE FACTS · {dateTime(ai.as_of)}</p>
              <div className="ai-facts">
                <span>{ai.facts.total} tasks</span>
                <span>{ai.facts.completed} complete</span>
                <span>{ai.facts.overdue} overdue</span>
              </div>
              <h3>
                <Sparkles size={16} />
                Generated suggestions
              </h3>
              <p className="ai-text">{ai.suggestions}</p>
              <p className="muted small">Suggestions are for review. No tasks have been changed.</p>
            </>
          )}
        </div>
      ) : modal.kind === 'dependencies' ? (
        <div>
          <p className="muted">
            Each arrow points from a prerequisite to the task it blocks. Inactive prerequisites remain
            unresolved.
          </p>
          <div className="dependency-map">
            {snapshot.dependencies
              .filter((d) => d.board_id === board?.id)
              .map((d) => {
                const prerequisite = snapshot.cards.find((c) => c.id === d.prerequisite_id),
                  dependent = snapshot.cards.find((c) => c.id === d.card_id)
                return (
                  <div className="dependency-edge" key={d.id}>
                    <button
                      disabled={!prerequisite}
                      onClick={() => {
                        onClose()
                        openCard(d.prerequisite_id)
                      }}
                    >
                      {prerequisite?.title || 'Deleted prerequisite'}
                      {(!prerequisite || prerequisite.inactive) && <small>Unresolved</small>}
                    </button>
                    <span aria-label="blocks">?</span>
                    <button
                      disabled={!dependent}
                      onClick={() => {
                        onClose()
                        openCard(d.card_id)
                      }}
                    >
                      {dependent?.title || 'Deleted task'}
                    </button>
                  </div>
                )
              })}
            {!snapshot.dependencies.some((d) => d.board_id === board?.id) && (
              <p className="muted">No dependencies yet. Link prerequisites from task details.</p>
            )}
          </div>
        </div>
      ) : modal.kind === 'activity' ? (
        <div>
          {error && <p role="alert">{error}</p>}
          {events.map((e) => (
            <div className="activity-row" key={e.id}>
              <Avatar name={e.actor_name} size="small" />
              <div>
                <strong>{e.actor_name}</strong> {actionLabel(e.action)}
                <small>{dateTime(e.created_at)}</small>
                <details>
                  <summary>Change details</summary>
                  <pre className="activity-data">{e.before_json + ' → ' + e.after_json}</pre>
                </details>
              </div>
            </div>
          ))}
          {!events.length && !error && <p className="muted">No activity yet.</p>}
          {events.length < total && (
            <button className="button" onClick={() => void loadActivity(events.length)}>
              Load more
            </button>
          )}
        </div>
      ) : link ? (
        <div className="invite-result">
          <h3>Your invitation is ready</h3>
          <p>
            Share this link with the intended teammate. It expires in seven days. After sign-in, the account
            may need your approval in Members.
          </p>
          <input aria-label="Invitation link" readOnly value={link} />
          <button
            className="button primary"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(link)
                notify('Invitation link copied')
              } catch {
                notify('Select and copy the invitation link.', true)
              }
            }}
          >
            <Copy size={15} />
            Copy invitation
          </button>
          <p className="muted small">
            This link is shown once. Revoke and create a new invitation if it is lost.
          </p>
        </div>
      ) : (
        <>
          <form onSubmit={submit}>
            {['board', 'card', 'list', 'board-settings'].includes(modal.kind) && (
              <Field
                label={
                  modal.kind === 'card' ? 'Task title' : modal.kind === 'list' ? 'List name' : 'Board name'
                }
              >
                <input
                  name="title"
                  autoFocus
                  defaultValue={modal.kind === 'board-settings' ? board?.title : ''}
                  required
                  maxLength={160}
                  placeholder={modal.kind === 'card' ? 'What needs to get done?' : 'Give it a clear name'}
                />
              </Field>
            )}
            {['board', 'card', 'board-settings', 'label'].includes(modal.kind) && (
              <Field label="Description">
                <textarea
                  name="description"
                  defaultValue={
                    modal.kind === 'board-settings' ? board?.description : label?.description || ''
                  }
                  rows={3}
                  maxLength={modal.kind === 'card' ? 20000 : modal.kind === 'label' ? 1000 : 10000}
                  placeholder="A little context goes a long way."
                />
              </Field>
            )}
            {['board', 'board-settings'].includes(modal.kind) && (
              <div className="form-grid">
                <Field label="Visibility">
                  <select name="visibility" defaultValue={board?.visibility || 'workspace'}>
                    <option value="workspace">Workspace members</option>
                    <option value="private">Private · invited members only</option>
                  </select>
                </Field>
                {colors}
              </div>
            )}
            {modal.kind === 'list' && (
              <Field label="Progress category">
                <select name="category">
                  <option value="TODO">To do</option>
                  <option value="IN_PROGRESS">In progress</option>
                  <option value="DONE">Completed</option>
                </select>
              </Field>
            )}
            {modal.kind === 'card' && (
              <>
                <Field label="List">
                  <select name="list" defaultValue={modal.listId} required>
                    {snapshot.lists
                      .filter((l) => l.board_id === board?.id && !l.archived)
                      .map((l) => (
                        <option key={l.id} value={l.id}>
                          {l.title}
                        </option>
                      ))}
                  </select>
                </Field>
                <div className="form-grid">
                  <Field label="Assignee">
                    <select name="assignee">
                      <option value="">Unassigned</option>
                      {eligibleMembers(snapshot, board!.id).map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Due date">
                    <input name="due" type="date" />
                  </Field>
                </div>
                <fieldset>
                  <legend>Labels</legend>
                  <div className="chips">
                    {snapshot.labels
                      .filter((l) => l.board_id === board?.id)
                      .map((l) => (
                        <label className={'chip ' + l.color} key={l.id}>
                          <input type="checkbox" name="labels" value={l.id} />
                          {l.name}
                        </label>
                      ))}
                  </div>
                </fieldset>
              </>
            )}
            {modal.kind === 'label' && (
              <>
                <Field label="Label name">
                  <input name="name" defaultValue={label?.name} required maxLength={80} />
                </Field>
                {colors}
              </>
            )}
            {modal.kind === 'invite' && (
              <>
                <Field label="Email address">
                  <input
                    name="email"
                    type="email"
                    required
                    placeholder="teammate@company.com"
                    maxLength={254}
                  />
                </Field>
                <Field label="Workspace role">
                  <select name="role">
                    <option value="MEMBER">Member · organize tasks and lists</option>
                    <option value="VIEWER">Viewer · read accessible work</option>
                  </select>
                </Field>
                <p className="muted">
                  An invitation grants workspace access. Private boards require a separate grant.
                </p>
              </>
            )}
            <div className="dialog-actions">
              <button type="button" className="button" onClick={onClose}>
                Cancel
              </button>
              <button className="button primary" disabled={busy}>
                {busy ? 'Saving…' : modal.kind === 'invite' ? 'Create invitation' : 'Save'}
              </button>
            </div>
          </form>
          {modal.kind === 'label' && (
            <section className="detail-section">
              <h3>Existing labels</h3>
              {snapshot.labels
                .filter((l) => l.board_id === board?.id)
                .map((l) => (
                  <div className="row" key={l.id}>
                    <span className={'chip ' + l.color}>{l.name}</span>
                    <button
                      className="text-button"
                      onClick={() => {
                        openModal({ kind: 'label', boardId: board?.id, labelId: l.id })
                      }}
                    >
                      Edit
                    </button>
                    <button
                      className="icon-button danger"
                      aria-label={'Delete label ' + l.name}
                      onClick={() => {
                        if (confirm('Remove this label from the board and every task?'))
                          void perform(
                            { action: 'delete_label', board_id: l.board_id, label_id: l.id },
                            'Label deleted'
                          )
                      }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
            </section>
          )}
          {modal.kind === 'board-settings' && board && (
            <>
              {board.visibility === 'private' && (
                <section className="detail-section">
                  <h3>Private board access</h3>
                  <p className="muted">
                    The owner always has access. Removing access also clears this member's assignments on the
                    board.
                  </p>
                  {snapshot.members
                    .filter((m) => m.role !== 'OWNER')
                    .map((m) => (
                      <label className="access-row" key={m.id}>
                        <input
                          type="checkbox"
                          checked={snapshot.board_members.some(
                            (g) => g.board_id === board.id && g.user_id === m.id
                          )}
                          onChange={(e) =>
                            void perform({
                              action: 'board_access',
                              board_id: board.id,
                              expected_version: board.version,
                              user_id: m.id,
                              allow: e.target.checked,
                            })
                          }
                        />
                        <Avatar name={m.name} size="small" />
                        {m.name}
                      </label>
                    ))}
                </section>
              )}
              <section className="detail-section danger-zone">
                <h3>Board lifecycle</h3>
                <button
                  className="button"
                  onClick={async () => {
                    if (
                      confirm(
                        board.archived
                          ? 'Restore this board?'
                          : 'Archive this board and hide its work from active views?'
                      )
                    ) {
                      const r = await perform({
                        action: board.archived ? 'restore_board' : 'archive_board',
                        board_id: board.id,
                        expected_version: board.version,
                      })
                      if (r) onClose()
                    }
                  }}
                >
                  {board.archived ? 'Restore board' : 'Archive board'}
                </button>
                <button
                  className="button danger"
                  onClick={async () => {
                    const confirmation = prompt('Type the board name to delete it: ' + board.title)
                    if (confirmation !== null) {
                      const r = await perform(
                        {
                          action: 'delete_board',
                          board_id: board.id,
                          expected_version: board.version,
                          confirmation,
                        },
                        'Board deleted'
                      )
                      if (r) {
                        onClose()
                        navigate('boards')
                      }
                    }
                  }}
                >
                  Delete board
                </button>
              </section>
            </>
          )}
        </>
      )}
    </Dialog>
  )
}
