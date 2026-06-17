"""Writing project routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.database.sqlite import Project, WritingProject
from app.models import (
    WritingProjectCreate,
    WritingProjectResponse,
    WritingProjectUpdate,
)
from app.services.latex_service import create_project, list_project_files, list_templates

router = APIRouter()


def _ensure_project(db: Session, project_id: str) -> None:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        return
    db.add(Project(
        id=project_id,
        name="Default" if project_id == "default" else project_id,
        description="Auto-created project for writing.",
    ))
    db.flush()


def _to_response(project: WritingProject) -> WritingProjectResponse:
    return WritingProjectResponse(
        id=project.id,
        project_id=project.project_id,
        title=project.title,
        target_venue=project.target_venue or "",
        language=project.language or "en",
        template=project.template or "",
        external_editor_path=project.external_editor_path or "",
        outline=project.outline or [],
        latex_project_path=project.latex_project_path or "",
        files=list_project_files(project.latex_project_path or ""),
        created_at=project.created_at,
    )


@router.get("/writing/templates")
def templates():
    return {"items": list_templates()}


@router.post("/writing/projects", response_model=WritingProjectResponse)
def create_writing_project(req: WritingProjectCreate, db: Session = Depends(get_db)):
    _ensure_project(db, req.project_id)
    latex_path = create_project(req.template, req.title, req.author)
    project = WritingProject(
        project_id=req.project_id,
        title=req.title,
        target_venue=req.target_venue,
        language=req.language,
        template=req.template,
        outline=[],
        latex_project_path=latex_path,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_response(project)


@router.get("/writing/projects")
def list_writing_projects(project_id: str = "default", db: Session = Depends(get_db)):
    items = (
        db.query(WritingProject)
        .filter(WritingProject.project_id == project_id)
        .order_by(WritingProject.created_at.desc())
        .all()
    )
    return {"items": [_to_response(item) for item in items]}


@router.get("/writing/projects/{project_id}", response_model=WritingProjectResponse)
def get_writing_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(WritingProject).filter(WritingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Writing project not found")
    return _to_response(project)


@router.patch("/writing/projects/{project_id}", response_model=WritingProjectResponse)
def update_writing_project(
    project_id: str,
    req: WritingProjectUpdate,
    db: Session = Depends(get_db),
):
    project = db.query(WritingProject).filter(WritingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Writing project not found")

    for field in (
        "title",
        "target_venue",
        "language",
        "template",
        "external_editor_path",
        "outline",
    ):
        value = getattr(req, field)
        if value is not None:
            setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return _to_response(project)


@router.post("/writing/projects/{project_id}/open")
def open_writing_project(project_id: str, db: Session = Depends(get_db)):
    """Return editor launch information for the frontend/Tauri shell layer."""
    project = db.query(WritingProject).filter(WritingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Writing project not found")

    editor = project.external_editor_path or "code"
    return {
        "path": project.latex_project_path,
        "editor": editor,
        "args": [project.latex_project_path],
        "message": "Use the Tauri shell layer or your OS shell to open this project.",
    }
