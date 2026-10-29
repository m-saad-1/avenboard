"""The web door: JSON routes plus one small page. Every route calls a use case and nothing else."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from boards.application.use_cases import Boards, NotFound
from boards.doors.identity import person_from
from boards.domain.model import Forbidden, Invalid, Person


def build_router(boards: Boards) -> APIRouter:
    r = APIRouter()

    def me(request: Request) -> Person:
        p = person_from(request.headers)
        if p is None:
            raise HTTPException(401, "sign in first: /.dodil/auth/login")
        return p

    def run(fn, *args):
        try:
            return fn(*args)
        except NotFound as e:
            raise HTTPException(404, str(e))
        except Forbidden as e:
            raise HTTPException(403, str(e))
        except Invalid as e:
            raise HTTPException(422, str(e))

    class Title(BaseModel):
        title: str

    class CardIn(BaseModel):
        title: str
        list_name: str = "To do"

    class Move(BaseModel):
        list_name: str

    class Member(BaseModel):
        email: str
        role: str = "member"

    @r.get("/api/boards")
    def my_boards(request: Request):
        return run(boards.my_boards, me(request))

    @r.post("/api/boards", status_code=201)
    def create_board(body: Title, request: Request):
        return run(boards.create_board, me(request), body.title)

    @r.get("/api/boards/{board_id}")
    def show_board(board_id: str, request: Request):
        return run(boards.show_board, me(request), board_id)

    @r.post("/api/boards/{board_id}/members", status_code=201)
    def add_member(board_id: str, body: Member, request: Request):
        return run(boards.add_member, me(request), board_id, body.email, body.role)

    @r.post("/api/boards/{board_id}/cards", status_code=201)
    def add_card(board_id: str, body: CardIn, request: Request):
        return run(boards.add_card, me(request), board_id, body.title, body.list_name)

    @r.post("/api/cards/{card_id}/move")
    def move_card(card_id: str, body: Move, request: Request):
        return run(boards.move_card, me(request), card_id, body.list_name)

    @r.post("/api/cards/{card_id}/checklist")
    def suggest_checklist(card_id: str, request: Request):
        return run(boards.suggest_checklist, me(request), card_id)

    @r.get("/", response_class=HTMLResponse)
    def page(request: Request):
        if person_from(request.headers) is None:
            return RedirectResponse("/.dodil/auth/login?return_to=/", status_code=303)
        return PAGE

    return r


# Deliberately tiny: it proves sign-in and the routes work. Replace it with your real board UI.
PAGE = """<!doctype html><meta charset=utf-8><title>Boards</title>
<style>body{font:15px system-ui;margin:2rem;max-width:56rem}.cols{display:flex;gap:1rem}
.col{flex:1;background:#f3f4f6;border-radius:8px;padding:.6rem;min-height:6rem}
.card{background:#fff;border-radius:6px;padding:.4rem .6rem;margin:.3rem 0}</style>
<h1>Boards starter</h1><p>Signed in through Dodil appid. <a href="/.dodil/auth/logout">Sign out</a></p>
<form id=nb><input id=t placeholder="New board title"> <button>Create board</button></form>
<ul id=list></ul><div id=board></div>
<script>
const j=(u,o)=>fetch(u,{headers:{'content-type':'application/json'},...o}).then(r=>r.json());
async function load(){const b=await j('/api/boards');list.innerHTML=b.map(x=>
 `<li><a href="#" onclick="show('${x.id}');return false">${x.title}</a> (${x.role})</li>`).join('')}
async function show(id){const b=await j('/api/boards/'+id);board.innerHTML=`<h2>${b.title}</h2>
 <form onsubmit="add(event,'${id}')"><input name=c placeholder="New card"> <button>Add</button></form>
 <div class=cols>${['To do','Doing','Done'].map(l=>`<div class=col><b>${l}</b>${b.cards
 .filter(c=>c.list_name==l).map(c=>`<div class=card>${c.title}<br><small>${['To do','Doing','Done']
 .filter(x=>x!=l).map(x=>`<a href="#" onclick="mv('${c.id}','${x}','${id}');return false">→ ${x}</a>`)
 .join(' ')}</small></div>`).join('')}</div>`).join('')}</div>`}
async function add(e,id){e.preventDefault();await j(`/api/boards/${id}/cards`,{method:'POST',
 body:JSON.stringify({title:e.target.c.value})});show(id)}
async function mv(c,l,id){await j(`/api/cards/${c}/move`,{method:'POST',body:JSON.stringify({list_name:l})});show(id)}
nb.onsubmit=async e=>{e.preventDefault();await j('/api/boards',{method:'POST',body:JSON.stringify({title:t.value})});t.value='';load()};
load();
</script>"""
