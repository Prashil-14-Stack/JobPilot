from typing import Optional

from pydantic import BaseModel, Field


class JobSource(BaseModel):

    name: str

    source_type: str

    domain: str

    search_url: Optional[str] = None

    api_available: Optional[bool] = None

    web_search_available: Optional[bool] = None

    structured_data_available: Optional[bool] = None

    access_method: Optional[str] = None

    discovered_from: Optional[str] = None

    confidence: Optional[float] = None

    rationale: Optional[str] = None

    # -----------------------------------------------------
    # Validation results
    # -----------------------------------------------------

    verified: bool = False

    reachable: Optional[bool] = None

    http_status: Optional[int] = None

    validation_error: Optional[str] = None

    validation_method: Optional[str] = None

from typing import Optional

from pydantic import BaseModel, Field


class JobSource(BaseModel):

    name: str

    source_type: str

    domain: str

    search_url: Optional[str] = None

    api_available: Optional[bool] = None

    web_search_available: Optional[bool] = None

    structured_data_available: Optional[bool] = None

    access_method: Optional[str] = None

    discovered_from: Optional[str] = None

    confidence: Optional[float] = None

    rationale: Optional[str] = None

    # -----------------------------------------------------
    # Validation results
    # -----------------------------------------------------

    verified: bool = False

    reachable: Optional[bool] = None

    http_status: Optional[int] = None

    validation_error: Optional[str] = None

    validation_method: Optional[str] = None


from typing import Optional

from pydantic import BaseModel, Field


class JobSource(BaseModel):

    name: str

    source_type: str

    domain: str

    search_url: Optional[str] = None

    api_available: Optional[bool] = None

    web_search_available: Optional[bool] = None

    structured_data_available: Optional[bool] = None

    access_method: Optional[str] = None

    discovered_from: Optional[str] = None

    confidence: Optional[float] = None

    rationale: Optional[str] = None

    # -----------------------------------------------------
    # Validation results
    # -----------------------------------------------------

    verified: bool = False

    reachable: Optional[bool] = None

    http_status: Optional[int] = None

    validation_error: Optional[str] = None

    validation_method: Optional[str] = None


class JobSource(BaseModel):

    name: str

    source_type: str

    domain: str

    search_url: Optional[str] = None

    api_available: Optional[bool] = None

    web_search_available: Optional[bool] = None

    structured_data_available: Optional[bool] = None

    access_method: Optional[str] = None

    discovered_from: Optional[str] = None

    confidence: Optional[float] = None

    rationale: Optional[str] = None

    # -----------------------------------------------------
    # Validation results
    # -----------------------------------------------------

    verified: bool = False

    reachable: Optional[bool] = None

    http_status: Optional[int] = None

    validation_error: Optional[str] = None

    validation_method: Optional[str] = None


class SourceRegistry(BaseModel):

    generated_at: str

    role_universe_version: str

    sources: list[JobSource] = Field(
        default_factory=list
    )