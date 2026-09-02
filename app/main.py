from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import get_connection, initialize_database
from app.ollama_client import DEFAULT_MODEL, OllamaError, generate_research_brief
from app.schemas import (
    ResearchBriefResponse,
    ResearchGenerationRequest,
    SourceRequest,
    SourceResponse,
    TopicRequest,
    TopicResponse,
)
from app.source_extractor import extract_page_text


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="StoryForge API",
    version="0.1.0",
    description="Local-first automation for documentary video production.",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    """Serve the first user-facing StoryForge screen."""
    return FileResponse("app/static/index.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Allow the app and future frontend to confirm that the API is available."""
    return {"status": "ok", "service": "storyforge-api"}


@app.post("/api/projects", response_model=TopicResponse, status_code=201)
def create_project(request: TopicRequest) -> TopicResponse:
    """Create and persist a documentary project from a topic."""
    clean_topic = request.topic.strip()
    project = TopicResponse(
        id=str(uuid4()),
        topic=clean_topic,
        status="created",
        created_at=datetime.now(timezone.utc),
    )
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO projects (id, topic, status, created_at)
            VALUES (:id, :topic, :status, :created_at)
            """,
            project.model_dump(mode="json"),
        )
    return project


@app.get("/api/projects", response_model=list[TopicResponse])
def list_projects() -> list[TopicResponse]:
    """Return the user's projects, newest first."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, topic, status, created_at FROM projects ORDER BY created_at DESC"
        ).fetchall()
    return [TopicResponse(**dict(row)) for row in rows]


@app.get("/api/projects/{project_id}", response_model=TopicResponse)
def get_project(project_id: str) -> TopicResponse:
    """Return one project by its unique identifier."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, topic, status, created_at
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return TopicResponse(**dict(row))


@app.get("/api/projects/{project_id}/sources", response_model=list[SourceResponse])
def list_sources(project_id: str) -> list[SourceResponse]:
    """List research sources saved for one project, newest first."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, project_id, title, url, notes, created_at, extracted_text, extracted_at
            FROM sources
            WHERE project_id = ?
            ORDER BY created_at DESC
            """,
            (project_id,),
        ).fetchall()
    return [SourceResponse(**dict(row)) for row in rows]


@app.post(
    "/api/projects/{project_id}/sources",
    response_model=SourceResponse,
    status_code=201,
)
def create_source(project_id: str, request: SourceRequest) -> SourceResponse:
    """Save a source after confirming that the project exists."""
    with get_connection() as connection:
        project_exists = connection.execute(
            "SELECT 1 FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project_exists is None:
            raise HTTPException(status_code=404, detail="Project not found")

        source = SourceResponse(
            id=str(uuid4()),
            project_id=project_id,
            title=request.title.strip(),
            url=request.url.strip(),
            notes=request.notes.strip(),
            created_at=datetime.now(timezone.utc),
        )
        connection.execute(
            """
            INSERT INTO sources (id, project_id, title, url, notes, created_at)
            VALUES (:id, :project_id, :title, :url, :notes, :created_at)
            """,
            source.model_dump(mode="json"),
        )
    return source


@app.delete("/api/projects/{project_id}/sources/{source_id}", status_code=204)
def delete_source(project_id: str, source_id: str) -> None:
    """Remove an irrelevant or duplicate research source from a project."""
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM sources WHERE id = ? AND project_id = ?",
            (source_id, project_id),
        )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Source not found")


@app.post(
    "/api/projects/{project_id}/sources/{source_id}/extract",
    response_model=SourceResponse,
)
def extract_source(project_id: str, source_id: str) -> SourceResponse:
    """Fetch the readable text of one saved public research source."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, project_id, title, url, notes, created_at, extracted_text, extracted_at
            FROM sources
            WHERE id = ? AND project_id = ?
            """,
            (source_id, project_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Source not found")

    try:
        extracted_text = extract_page_text(row["url"])
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    extracted_at = datetime.now(timezone.utc)
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE sources
            SET extracted_text = ?, extracted_at = ?
            WHERE id = ? AND project_id = ?
            """,
            (extracted_text, extracted_at.isoformat(), source_id, project_id),
        )
        updated_row = connection.execute(
            """
            SELECT id, project_id, title, url, notes, created_at, extracted_text, extracted_at
            FROM sources
            WHERE id = ? AND project_id = ?
            """,
            (source_id, project_id),
        ).fetchone()
    return SourceResponse(**dict(updated_row))


@app.post(
    "/api/projects/{project_id}/research/generate",
    response_model=ResearchBriefResponse,
)
def generate_project_research(
    project_id: str, request: ResearchGenerationRequest
) -> ResearchBriefResponse:
    """Generate and save a citation-oriented research brief from extracted sources."""
    with get_connection() as connection:
        project = connection.execute(
            "SELECT id, topic FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        source_rows = connection.execute(
            """
            SELECT title, url, extracted_text
            FROM sources
            WHERE project_id = ? AND extracted_text IS NOT NULL
            ORDER BY created_at
            """,
            (project_id,),
        ).fetchall()

    if not source_rows:
        raise HTTPException(
            status_code=409,
            detail="Extract text from at least one source before generating research.",
        )

    try:
        content = generate_research_brief(
            project["topic"], [dict(row) for row in source_rows], request.language
        )
    except OllamaError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    generated_at = datetime.now(timezone.utc)
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE projects
            SET research_brief = ?, research_generated_at = ?, research_model = ?, research_language = ?
            WHERE id = ?
            """,
            (
                content,
                generated_at.isoformat(),
                DEFAULT_MODEL,
                request.language,
                project_id,
            ),
        )
    return ResearchBriefResponse(
        project_id=project_id,
        content=content,
        language=request.language,
        model=DEFAULT_MODEL,
        generated_at=generated_at,
    )


@app.get(
    "/api/projects/{project_id}/research",
    response_model=ResearchBriefResponse,
)
def get_project_research(project_id: str) -> ResearchBriefResponse:
    """Return the most recently saved research brief for a project."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT research_brief, research_generated_at, research_model, research_language
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if row["research_brief"] is None:
        raise HTTPException(status_code=404, detail="No research brief has been generated yet")
    return ResearchBriefResponse(
        project_id=project_id,
        content=row["research_brief"],
        language=row["research_language"],
        model=row["research_model"],
        generated_at=row["research_generated_at"],
    )
