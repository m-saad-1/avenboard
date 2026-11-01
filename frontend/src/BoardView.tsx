import { useState } from 'react'
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  closestCorners,
  pointerWithin,
  DragOverlay,
  type DragEndEvent,
  type CollisionDetection,
} from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  horizontalListSortingStrategy,
  sortableKeyboardCoordinates,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  Plus,
  GripVertical,
  MoreHorizontal,
  Search,
  SlidersHorizontal,
  Star,
  Lock,
  ArrowUpRight,
  CheckSquare,
  CalendarDays,
  GitBranch,
  Sparkles,
  Archive,
  ArrowUp,
  ArrowDown,
} from 'lucide-react'
import type { Card, Lane, Board } from './types'
import { useWorkspace } from './context'
import { Avatar, Due, Empty, Field, Dialog } from './ui'

const collision: CollisionDetection = (args) => {
  const hits = args.pointerCoordinates ? pointerWithin(args) : closestCorners(args)
  const kind = args.active.data.current?.kind
  if (kind === 'list') return hits.filter((h) => String(h.id).startsWith('list:'))
  if (!args.pointerCoordinates) return hits
  const cards = hits.filter((h) => String(h.id).startsWith('card:'))
  return cards.length ? cards : hits
}

function CardTile({
  card,
  disabled = false,
  overlay = false,
}: {
  card: Card
  disabled?: boolean
  overlay?: boolean
}) {
  const { snapshot, openCard } = useWorkspace()
  const sortable = useSortable({
    id: (overlay ? 'overlay:' : 'card:') + card.id,
    data: { kind: 'card', card },
    disabled: disabled || overlay,
  })
  const user = snapshot.members.find((m) => m.id === card.assignee_id)
  const labels = snapshot.labels.filter((l) => card.label_ids.includes(l.id))
  const blocking = snapshot.dependencies.some((d) => d.card_id === card.id)
  return (
    <article
      aria-hidden={overlay || undefined}
      inert={overlay || undefined}
      ref={sortable.setNodeRef}
      style={{
        transform: CSS.Transform.toString(sortable.transform),
        transition: sortable.transition,
        opacity: sortable.isDragging ? 0.35 : 1,
      }}
      className={'task-card ' + (overlay ? 'drag-overlay' : '')}
      data-card={card.id}
    >
      <div className="card-top">
        <span className="card-number">AV-{card.number}</span>
        {!disabled && (
          <button
            {...sortable.attributes}
            {...sortable.listeners}
            className="drag-handle"
            aria-label={'Drag ' + card.title}
          >
            <GripVertical size={14} />
          </button>
        )}
      </div>
      <button className="card-title" onClick={() => openCard(card.id)}>
        {card.title}
      </button>
      {labels.length > 0 && (
        <div className="chips">
          {labels.map((l) => (
            <span key={l.id} className={'chip ' + l.color}>
              {l.name}
            </span>
          ))}
        </div>
      )}
      <div className="card-bottom">
        <div className="card-meta">
          {card.due_date && (
            <span>
              <CalendarDays size={13} />
              <Due value={card.due_date} overdue={card.overdue} />
            </span>
          )}
          {card.checklist.length > 0 && (
            <span title="Checklist progress">
              <CheckSquare size={13} />
              {card.checklist.filter((i) => i.completed).length}/{card.checklist.length}
            </span>
          )}
          {blocking && (
            <span title="Has dependencies">
              <GitBranch size={13} />
            </span>
          )}
        </div>
        {user ? (
          <Avatar name={user.name} size="small" />
        ) : (
          <span className="unassigned" title="Unassigned">
            —
          </span>
        )}
      </div>
    </article>
  )
}
function Column({ lane, cards, disabled }: { lane: Lane; cards: Card[]; disabled: boolean }) {
  const { snapshot, perform, openModal } = useWorkspace()
  const sortable = useSortable({ id: 'list:' + lane.id, data: { kind: 'list', lane }, disabled })
  const [quick, setQuick] = useState(false),
    [text, setText] = useState(''),
    [edit, setEdit] = useState(false),
    [busy, setBusy] = useState(false)
  const canEdit = snapshot.role !== 'VIEWER'
  async function add() {
    if (!text.trim()) return
    setBusy(true)
    const r = await perform({ action: 'create_card', list_id: lane.id, title: text }, 'Card created')
    setBusy(false)
    if (r) {
      setText('')
      setQuick(false)
    }
  }
  async function reorder(direction: number) {
    const board = snapshot.boards.find((b) => b.id === lane.board_id)!
    const lanes = snapshot.lists.filter((l) => l.board_id === lane.board_id && !l.archived)
    const index = lanes.findIndex((l) => l.id === lane.id),
      next = index + direction
    if (next >= 0 && next < lanes.length)
      await perform({
        action: 'reorder_lists',
        board_id: board.id,
        expected_version: board.version,
        list_ids: arrayMove(lanes, index, next).map((l) => l.id),
      })
  }
  return (
    <section
      ref={sortable.setNodeRef}
      style={{ transform: CSS.Transform.toString(sortable.transform), transition: sortable.transition }}
      className={'board-column ' + (sortable.isOver ? 'drop-over' : '')}
      aria-label={lane.title}
    >
      <header className="column-header">
        <span className={'status-dot ' + lane.category} />
        <h3>{lane.title}</h3>
        <span className="count">{cards.length}</span>
        <span className="column-actions">
          {!disabled && (
            <button
              className="icon-button compact"
              {...sortable.attributes}
              {...sortable.listeners}
              aria-label={'Drag list ' + lane.title}
            >
              <GripVertical size={14} />
            </button>
          )}
          {canEdit && (
            <button
              className="icon-button compact"
              aria-label={'List settings ' + lane.title}
              onClick={() => setEdit(true)}
            >
              <MoreHorizontal size={18} />
            </button>
          )}
        </span>
      </header>
      <SortableContext items={cards.map((c) => 'card:' + c.id)} strategy={verticalListSortingStrategy}>
        <div className="column-cards">
          {cards.map((c) => (
            <CardTile key={c.id} card={c} disabled={disabled} />
          ))}
          {!cards.length && <div className="drop-empty">A little room for what's next</div>}
        </div>
      </SortableContext>
      {canEdit &&
        (quick ? (
          <form
            className="quick-add"
            onSubmit={(e) => {
              e.preventDefault()
              void add()
            }}
          >
            <input
              autoFocus
              aria-label="New task title"
              placeholder="What needs to get done?"
              value={text}
              maxLength={160}
              onChange={(e) => setText(e.target.value)}
            />
            <div>
              <button className="button primary small" disabled={busy}>
                Add task
              </button>
              <button className="button small quiet" type="button" onClick={() => setQuick(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button className="add-task" onClick={() => setQuick(true)}>
            <Plus size={16} />
            Add task
          </button>
        ))}
      {edit && (
        <Dialog title="List settings" onClose={() => setEdit(false)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault()
              const f = new FormData(e.currentTarget)
              const result = await perform(
                {
                  action: 'update_list',
                  list_id: lane.id,
                  expected_version: lane.version,
                  title: String(f.get('title')),
                  category: String(f.get('category')) as Lane['category'],
                },
                'List updated'
              )
              if (result) setEdit(false)
            }}
          >
            <Field label="List name">
              <input name="title" defaultValue={lane.title} required maxLength={160} />
            </Field>
            <Field label="Progress category">
              <select name="category" defaultValue={lane.category}>
                <option value="TODO">To do</option>
                <option value="IN_PROGRESS">In progress</option>
                <option value="DONE">Completed</option>
              </select>
            </Field>
            <p className="muted">The category determines progress, even when you rename the list.</p>
            <div className="dialog-actions">
              <button type="button" className="button" disabled={disabled} onClick={() => void reorder(-1)}>
                <ArrowUp size={15} />
                Move left
              </button>
              <button type="button" className="button" disabled={disabled} onClick={() => void reorder(1)}>
                <ArrowDown size={15} />
                Move right
              </button>
              <button className="button primary">Save</button>
            </div>
            <button
              type="button"
              className="danger-link"
              onClick={async () => {
                if (confirm('Archive this list and hide its cards from active views?')) {
                  const r = await perform(
                    { action: 'archive_list', list_id: lane.id, expected_version: lane.version },
                    'List archived'
                  )
                  if (r) setEdit(false)
                }
              }}
            >
              <Archive size={14} />
              Archive list and its contents
            </button>
          </form>
        </Dialog>
      )}
    </section>
  )
}
export default function BoardView({ board }: { board: Board }) {
  const { snapshot, user, perform, setSnapshot, openModal, refresh } = useWorkspace()
  const [query, setQuery] = useState(''),
    [assignee, setAssignee] = useState(''),
    [label, setLabel] = useState(''),
    [due, setDue] = useState(''),
    [status, setStatus] = useState(''),
    [filters, setFilters] = useState(false),
    [dragged, setDragged] = useState<Card | null>(null),
    [showArchive, setShowArchive] = useState(false),
    [listFilter, setListFilter] = useState(''),
    [fromDate, setFromDate] = useState(''),
    [toDate, setToDate] = useState('')
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )
  const filtered = !!(query || assignee || label || due || status || listFilter || fromDate || toDate)
  const disabled = snapshot.role === 'VIEWER' || filtered || board.archived
  const all = snapshot.cards.filter((c) => c.board_id === board.id)
  const cards = all.filter(
    (c) =>
      !c.inactive &&
      (!query || (c.title + ' ' + c.description).toLowerCase().includes(query.toLowerCase())) &&
      (!assignee || c.assignee_id === assignee) &&
      (!label || c.label_ids.includes(label)) &&
      (!due || (due === 'overdue' ? c.overdue : c.due_soon)) &&
      (!status || c.status === status) &&
      (!listFilter || c.list_id === listFilter) &&
      (!fromDate || (!!c.due_date && c.due_date >= fromDate)) &&
      (!toDate || (!!c.due_date && c.due_date <= toDate))
  )
  const lanes = snapshot.lists.filter((l) => l.board_id === board.id && !l.archived)
  const favored = snapshot.favorites.includes(board.id)
  async function dragEnd(event: DragEndEvent) {
    setDragged(null)
    if (disabled || !event.over || event.active.id === event.over.id) return
    const a = event.active.data.current,
      o = event.over.data.current
    if (a?.kind === 'list' && (o?.kind === 'list' || o?.kind === 'card')) {
      const from = lanes.findIndex((l) => l.id === a.lane.id),
        to = lanes.findIndex((l) => l.id === (o.kind === 'card' ? o.card.list_id : o.lane.id))
      await perform({
        action: 'reorder_lists',
        board_id: board.id,
        expected_version: board.version,
        list_ids: arrayMove(lanes, from, to).map((l) => l.id),
      })
    } else if (a?.kind === 'card') {
      const card = a.card as Card,
        target = o?.kind === 'card' ? o.card.list_id : o?.lane?.id
      if (!target) return
      const targetCards = cards.filter((c) => c.list_id === target)
      const position =
        o?.kind === 'card' ? targetCards.findIndex((c) => c.id === o.card.id) : targetCards.length
      const before = snapshot
      setSnapshot({
        ...snapshot,
        cards: snapshot.cards.map((c) => (c.id === card.id ? { ...c, list_id: target, position } : c)),
      })
      const result = await perform({
        action: 'move_card',
        card_id: card.id,
        expected_version: card.version,
        list_id: target,
        position,
      })
      if (!result) {
        setSnapshot(before)
        await refresh()
      }
    }
  }
  return (
    <div className="board-view">
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR WORK, IN MOTION</div>
          <div className="heading-line">
            <h1>{board.title}</h1>
            <button
              className={'icon-button ' + (favored ? 'favorited' : '')}
              aria-label={favored ? 'Remove favorite' : 'Favorite board'}
              onClick={() => void perform({ action: 'favorite', board_id: board.id, value: !favored })}
            >
              <Star size={20} fill={favored ? 'currentColor' : 'none'} />
            </button>
            {board.visibility === 'private' && <Lock size={16} />}
          </div>
          <p>{board.description || 'A shared space to turn plans into progress.'}</p>
        </div>
        <div className="heading-actions">
          <button
            className="button"
            onClick={() => openModal({ kind: 'ai', boardId: board.id, aiKind: 'summary' })}
          >
            <Sparkles size={16} />
            Board summary
          </button>
          {snapshot.role === 'OWNER' && (
            <button
              className="icon-button bordered"
              aria-label="Board settings"
              onClick={() => openModal({ kind: 'board-settings', boardId: board.id })}
            >
              <MoreHorizontal size={20} />
            </button>
          )}
        </div>
      </div>
      <div className="board-toolbar">
        <div className="board-tabs">
          <span className="selected">Board</span>
          <button
            aria-label="Dependency map"
            onClick={() => openModal({ kind: 'dependencies', boardId: board.id })}
          >
            <GitBranch size={14} />
          </button>
          <button onClick={() => openModal({ kind: 'activity', boardId: board.id })}>Activity</button>
          <button onClick={() => setShowArchive(!showArchive)}>
            {showArchive ? 'Hide archive' : 'Archive'}
          </button>
        </div>
        <div className="toolbar-actions">
          {snapshot.role !== 'VIEWER' && (
            <button className="button small" onClick={() => openModal({ kind: 'label', boardId: board.id })}>
              Labels
            </button>
          )}
          <button
            className="button small"
            onClick={() => openModal({ kind: 'ai', boardId: board.id, aiKind: 'recommendations' })}
            aria-label="AI recommendations"
          >
            <Sparkles size={14} />
          </button>
          <div className="avatar-stack">
            {snapshot.members
              .filter(
                (m) =>
                  board.visibility === 'workspace' ||
                  m.role === 'OWNER' ||
                  snapshot.board_members.some((g) => g.board_id === board.id && g.user_id === m.id)
              )
              .slice(0, 4)
              .map((m) => (
                <Avatar key={m.id} name={m.name} size="small" />
              ))}
          </div>
          <button
            className={'button small ' + (filters ? 'active' : '')}
            onClick={() => setFilters(!filters)}
          >
            <SlidersHorizontal size={14} />
            Filter{filtered && <i className="active-dot" />}
          </button>
          {snapshot.role !== 'VIEWER' && !board.archived && (
            <button
              className="button primary small"
              onClick={() => openModal({ kind: 'card', boardId: board.id, listId: lanes[0]?.id })}
            >
              <Plus size={15} />
              New task
            </button>
          )}
        </div>
      </div>
      {filters && (
        <div className="filter-bar">
          <label className="search-field">
            <Search size={15} />
            <input
              aria-label="Search board"
              placeholder="Search tasks…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <select aria-label="Assignee filter" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
            <option value="">All members</option>
            <option value={user.id}>Assigned to me</option>
            {snapshot.members
              .filter((m) => m.id !== user.id)
              .map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
          </select>
          <select aria-label="Label filter" value={label} onChange={(e) => setLabel(e.target.value)}>
            <option value="">All labels</option>
            {snapshot.labels
              .filter((l) => l.board_id === board.id)
              .map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
          </select>
          <select aria-label="Due date filter" value={due} onChange={(e) => setDue(e.target.value)}>
            <option value="">Any due date</option>
            <option value="soon">Due soon</option>
            <option value="overdue">Overdue</option>
          </select>
          <select aria-label="Status filter" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any status</option>
            <option value="TODO">To do</option>
            <option value="IN_PROGRESS">In progress</option>
            <option value="DONE">Completed</option>
          </select>
          <select aria-label="List filter" value={listFilter} onChange={(e) => setListFilter(e.target.value)}>
            <option value="">All lists</option>
            {lanes.map((l) => (
              <option key={l.id} value={l.id}>
                {l.title}
              </option>
            ))}
          </select>
          <label className="date-filter">
            From
            <input
              type="date"
              aria-label="Due on or after"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
            />
          </label>
          <label className="date-filter">
            To
            <input
              type="date"
              aria-label="Due on or before"
              min={fromDate}
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
            />
          </label>
          <button
            className="text-button"
            onClick={() => {
              setListFilter('')
              setFromDate('')
              setToDate('')
              setQuery('')
              setAssignee('')
              setLabel('')
              setDue('')
              setStatus('')
            }}
          >
            Clear
          </button>
        </div>
      )}
      {filtered && (
        <p className="filter-note">
          Showing {cards.length} tasks. Clear filters to reorder; you can still move tasks from their details.
        </p>
      )}
      {board.archived ? (
        <Empty title="This board is archived">Restore it from board settings to resume work.</Empty>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={collision}
          accessibility={{
            screenReaderInstructions: {
              draggable:
                'Press Space to pick up. Use arrow keys to choose a position, Space to drop, or Escape to cancel.',
            },
            announcements: {
              onDragStart: ({ active }) =>
                `Picked up ${active.data.current?.card?.title || active.data.current?.lane?.title || 'item'}.`,
              onDragOver: ({ over }) =>
                over
                  ? `Over ${over.data.current?.card?.title || over.data.current?.lane?.title || 'drop target'}.`
                  : 'Outside a drop target.',
              onDragEnd: ({ over }) =>
                over
                  ? `Dropped on ${over.data.current?.card?.title || over.data.current?.lane?.title || 'drop target'}.`
                  : 'Move cancelled.',
              onDragCancel: () => 'Move cancelled.',
            },
          }}
          onDragStart={(e) => setDragged(e.active.data.current?.card || null)}
          onDragCancel={() => setDragged(null)}
          onDragEnd={(e) => void dragEnd(e)}
        >
          <SortableContext items={lanes.map((l) => 'list:' + l.id)} strategy={horizontalListSortingStrategy}>
            <div className="kanban">
              {lanes.map((l) => (
                <Column
                  key={l.id}
                  lane={l}
                  cards={cards.filter((c) => c.list_id === l.id)}
                  disabled={disabled}
                />
              ))}
              {snapshot.role !== 'VIEWER' && (
                <button className="new-list" onClick={() => openModal({ kind: 'list', boardId: board.id })}>
                  <Plus size={17} />
                  Add list
                </button>
              )}
            </div>
          </SortableContext>
          <DragOverlay>{dragged && <CardTile card={dragged} overlay />}</DragOverlay>
        </DndContext>
      )}
      {showArchive && (
        <section className="archive-panel">
          <h3>Archived items</h3>
          {snapshot.lists
            .filter((l) => l.board_id === board.id && l.archived)
            .map((l) => (
              <div className="row" key={l.id}>
                <span>List · {l.title}</span>
                {snapshot.role !== 'VIEWER' && (
                  <button
                    className="button small"
                    onClick={() =>
                      void perform({ action: 'restore_list', list_id: l.id, expected_version: l.version })
                    }
                  >
                    Restore list
                  </button>
                )}
              </div>
            ))}
          {all
            .filter((c) => c.archived)
            .map((c) => (
              <div className="row" key={c.id}>
                <span>{c.title}</span>
                {snapshot.role !== 'VIEWER' && (
                  <button
                    className="button small"
                    onClick={() =>
                      void perform({ action: 'restore_card', card_id: c.id, expected_version: c.version })
                    }
                  >
                    Restore card
                  </button>
                )}
              </div>
            ))}
          {!all.some((c) => c.archived) &&
            !snapshot.lists.some((l) => l.board_id === board.id && l.archived) && (
              <p className="muted">Nothing archived here.</p>
            )}
        </section>
      )}
    </div>
  )
}
