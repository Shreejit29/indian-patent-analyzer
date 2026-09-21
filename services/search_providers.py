"""
services/search_providers.py

Indian Patent Analyzer
Provider adapter layer for external patent-search sources.

Version: 3.0.0

Design principles
-----------------
1. Provider-specific logic stays outside the core search engine.
2. No API keys are hard-coded.
3. Public search pages are treated as link/manual providers unless
   a documented API endpoint is explicitly configured.
4. External results are normalized into a common structure.
5. Network failures must not crash the complete analysis pipeline.
6. Provider retrieval is evidence acquisition only; it does not establish
   novelty, inventive step, validity, infringement, or any legal conclusion.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


SEARCH_PROVIDERS_VERSION = "3.0.0"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROVIDER_GOOGLE_PATENTS = "google_patents"
PROVIDER_ESPACENET = "espacenet"
PROVIDER_WIPO = "wipo_patentscope"
PROVIDER_GENERIC_JSON = "generic_json_api"
PROVIDER_LOCAL_JSON = "local_json"


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_RETRIES = 2
DEFAULT_MAX_RESULTS = 20

DEFAULT_USER_AGENT = (
    "IndianPatentAnalyzer/3.0 "
    "(research-use; patent-search-provider-adapter)"
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ProviderConfig:
    """
    Configuration for a search provider.

    endpoint:
        Optional API endpoint. Public web providers normally do not require
        this and should be used through their search URL.

    api_key_env:
        Name of an environment variable containing the API key.

    headers:
        Optional additional HTTP headers.

    timeout:
        Network timeout in seconds.

    retries:
        Number of retries for transient network failures.

    enabled:
        Whether this provider is available to the registry.
    """

    name: str
    display_name: str
    endpoint: Optional[str] = None
    api_key_env: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    retries: int = DEFAULT_RETRIES
    enabled: bool = True


@dataclass
class ProviderSearchResult:
    """
    Provider-neutral representation of one external search result.
    """

    provider: str
    title: str = ""
    patent_number: str = ""
    publication_number: str = ""
    application_number: str = ""
    url: str = ""
    abstract: str = ""
    snippet: str = ""
    filing_date: str = ""
    publication_date: str = ""
    priority_date: str = ""
    applicants: List[str] = field(default_factory=list)
    inventors: List[str] = field(default_factory=list)
    assignees: List[str] = field(default_factory=list)
    classifications: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0
    retrieval_status: str = "retrieved"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderSearchResponse:
    """
    Complete provider response.
    """

    provider: str
    query: str
    results: List[ProviderSearchResult] = field(default_factory=list)
    success: bool = True
    status_code: Optional[int] = None
    error: Optional[str] = None
    elapsed_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "success": self.success,
            "status_code": self.status_code,
            "error": self.error,
            "elapsed_seconds": self.elapsed_seconds,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _clean(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, (list, tuple, set)):
        return "; ".join(
            _clean(item)
            for item in value
            if _clean(item)
        )

    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)

    return " ".join(str(value).split()).strip()


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, str):
        value = value.replace("|", ";").replace(",", ";")
        return [
            item.strip()
            for item in value.split(";")
            if item.strip()
        ]

    if isinstance(value, (list, tuple, set)):
        result = []
        for item in value:
            cleaned = _clean(item)
            if cleaned:
                result.append(cleaned)
        return result

    cleaned = _clean(value)
    return [cleaned] if cleaned else []


def _first(data: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in data:
            value = data[key]
            if value not in (None, "", [], {}):
                return value
    return None


def _absolute_url(base_url: str, query: str) -> str:
    encoded = urllib.parse.quote_plus(query.strip())
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}q={encoded}"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


class HTTPClient:
    """
    Small dependency-free HTTP client.

    Uses urllib so the provider layer does not force an additional dependency.
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        retries: int = DEFAULT_RETRIES,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.timeout = timeout
        self.retries = max(0, retries)
        self.user_agent = user_agent

    def get_json(
        self,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        request_headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

        if headers:
            request_headers.update(dict(headers))

        if api_key:
            request_headers["Authorization"] = f"Bearer {api_key}"

        last_error: Optional[Exception] = None

        for attempt in range(self.retries + 1):
            try:
                request = urllib.request.Request(
                    url,
                    headers=request_headers,
                    method="GET",
                )

                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:
                    raw = response.read().decode(
                        "utf-8",
                        errors="replace",
                    )

                    if not raw.strip():
                        return {}

                    return json.loads(raw)

            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc

                if attempt < self.retries:
                    time.sleep(0.5 * (attempt + 1))

        raise RuntimeError(
            f"Provider request failed: {last_error}"
        )


# ---------------------------------------------------------------------------
# Base provider
# ---------------------------------------------------------------------------


class PatentSearchProvider:
    """
    Base class for all patent search providers.

    Subclasses may implement:
        search()
        health_check()

    A provider should never claim legal significance for its own results.
    """

    provider_name = "base"
    display_name = "Base Provider"

    def __init__(
        self,
        config: Optional[ProviderConfig] = None,
        http_client: Optional[HTTPClient] = None,
    ) -> None:
        self.config = config or ProviderConfig(
            name=self.provider_name,
            display_name=self.display_name,
        )

        self.http = http_client or HTTPClient(
            timeout=self.config.timeout,
            retries=self.config.retries,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled)

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        **kwargs: Any,
    ) -> ProviderSearchResponse:
        raise NotImplementedError

    def health_check(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "available": self.enabled,
            "status": "configured" if self.enabled else "disabled",
        }

    def _api_key(self) -> Optional[str]:
        if not self.config.api_key_env:
            return None

        return os.getenv(self.config.api_key_env)

    def _response_error(
        self,
        query: str,
        error: Exception,
        elapsed: float,
    ) -> ProviderSearchResponse:
        return ProviderSearchResponse(
            provider=self.provider_name,
            query=query,
            results=[],
            success=False,
            error=str(error),
            elapsed_seconds=elapsed,
        )


# ---------------------------------------------------------------------------
# Public web providers
# ---------------------------------------------------------------------------


class GooglePatentsProvider(PatentSearchProvider):
    """
    Google Patents provider.

    This adapter deliberately does not scrape the Google Patents website.

    It generates a stable search URL and returns it as a provider result.
    Actual document retrieval should be handled through an approved API,
    browser workflow, or a user-selected source.

    This avoids fragile HTML scraping and respects provider-specific
    access constraints.
    """

    provider_name = PROVIDER_GOOGLE_PATENTS
    display_name = "Google Patents"

    SEARCH_URL = "https://patents.google.com/"

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        **kwargs: Any,
    ) -> ProviderSearchResponse:
        start = time.perf_counter()

        url = _absolute_url(self.SEARCH_URL, query)

        result = ProviderSearchResult(
            provider=self.provider_name,
            title=f"Google Patents search: {query}",
            url=url,
            snippet=(
                "Manual/provider search link generated. "
                "No website scraping was performed."
            ),
            retrieval_status="search_link",
        )

        return ProviderSearchResponse(
            provider=self.provider_name,
            query=query,
            results=[result],
            success=True,
            elapsed_seconds=time.perf_counter() - start,
            metadata={
                "mode": "search_link",
                "external_retrieval_required": True,
            },
        )


class EspacenetProvider(PatentSearchProvider):
    """
    Espacenet provider.

    Uses a generated search URL rather than undocumented HTML scraping.
    """

    provider_name = PROVIDER_ESPACENET
    display_name = "Espacenet"

    SEARCH_URL = (
        "https://worldwide.espacenet.com/patent/search/"
    )

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        **kwargs: Any,
    ) -> ProviderSearchResponse:
        start = time.perf_counter()

        url = _absolute_url(self.SEARCH_URL, query)

        result = ProviderSearchResult(
            provider=self.provider_name,
            title=f"Espacenet search: {query}",
            url=url,
            snippet=(
                "Manual/provider search link generated. "
                "No website scraping was performed."
            ),
            retrieval_status="search_link",
        )

        return ProviderSearchResponse(
            provider=self.provider_name,
            query=query,
            results=[result],
            success=True,
            elapsed_seconds=time.perf_counter() - start,
            metadata={
                "mode": "search_link",
                "external_retrieval_required": True,
            },
        )


class WIPOPatentscopeProvider(PatentSearchProvider):
    """
    WIPO PATENTSCOPE provider.

    Generates a search URL without scraping the public interface.
    """

    provider_name = PROVIDER_WIPO
    display_name = "WIPO PATENTSCOPE"

    SEARCH_URL = (
        "https://patentscope.wipo.int/search/en/result.jsf"
    )

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        **kwargs: Any,
    ) -> ProviderSearchResponse:
        start = time.perf_counter()

        url = _absolute_url(self.SEARCH_URL, query)

        result = ProviderSearchResult(
            provider=self.provider_name,
            title=f"WIPO PATENTSCOPE search: {query}",
            url=url,
            snippet=(
                "Manual/provider search link generated. "
                "No website scraping was performed."
            ),
            retrieval_status="search_link",
        )

        return ProviderSearchResponse(
            provider=self.provider_name,
            query=query,
            results=[result],
            success=True,
            elapsed_seconds=time.perf_counter() - start,
            metadata={
                "mode": "search_link",
                "external_retrieval_required": True,
            },
        )


# ---------------------------------------------------------------------------
# Generic JSON API provider
# ---------------------------------------------------------------------------


class GenericJSONAPIProvider(PatentSearchProvider):
    """
    Generic adapter for a documented JSON patent-search API.

    Expected response shapes are intentionally flexible.

    Supported common structures:

        {
            "results": [...]
        }

        {
            "items": [...]
        }

        {
            "data": [...]
        }

        {
            "documents": [...]
        }

    Endpoint may optionally contain `{query}`:

        https://example.com/search?q={query}

    Otherwise the query is appended as ?q=...
    """

    provider_name = PROVIDER_GENERIC_JSON
    display_name = "Generic JSON Patent API"

    RESULT_KEYS = (
        "results",
        "items",
        "data",
        "documents",
        "records",
    )

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        **kwargs: Any,
    ) -> ProviderSearchResponse:
        start = time.perf_counter()

        if not self.config.endpoint:
            return self._response_error(
                query,
                ValueError(
                    "No API endpoint configured for generic JSON provider."
                ),
                time.perf_counter() - start,
            )

        endpoint = self.config.endpoint

        encoded_query = urllib.parse.quote_plus(query)

        if "{query}" in endpoint:
            url = endpoint.replace(
                "{query}",
                encoded_query,
            )
        else:
            separator = "&" if "?" in endpoint else "?"
            url = f"{endpoint}{separator}q={encoded_query}"

        try:
            payload = self.http.get_json(
                url=url,
                headers=self.config.headers,
                api_key=self._api_key(),
            )

            raw_results = self._extract_results(payload)

            normalized = [
                self._normalize_result(item)
                for item in raw_results[:max_results]
            ]

            return ProviderSearchResponse(
                provider=self.provider_name,
                query=query,
                results=normalized,
                success=True,
                elapsed_seconds=time.perf_counter() - start,
                metadata={
                    "mode": "json_api",
                    "returned_results": len(normalized),
                },
            )

        except Exception as exc:
            return self._response_error(
                query,
                exc,
                time.perf_counter() - start,
            )

    def _extract_results(
        self,
        payload: Any,
    ) -> List[Mapping[str, Any]]:
        if isinstance(payload, list):
            return [
                item for item in payload
                if isinstance(item, Mapping)
            ]

        if not isinstance(payload, Mapping):
            return []

        for key in self.RESULT_KEYS:
            value = payload.get(key)

            if isinstance(value, list):
                return [
                    item for item in value
                    if isinstance(item, Mapping)
                ]

        return []

    def _normalize_result(
        self,
        item: Mapping[str, Any],
    ) -> ProviderSearchResult:
        title = _clean(
            _first(
                item,
                (
                    "title",
                    "document_title",
                    "patent_title",
                    "name",
                ),
            )
        )

        publication_number = _clean(
            _first(
                item,
                (
                    "publication_number",
                    "publicationNumber",
                    "publication",
                    "pub_number",
                    "document_number",
                ),
            )
        )

        patent_number = _clean(
            _first(
                item,
                (
                    "patent_number",
                    "patentNumber",
                    "patent_no",
                ),
            )
        )

        application_number = _clean(
            _first(
                item,
                (
                    "application_number",
                    "applicationNumber",
                    "application_no",
                ),
            )
        )

        url = _clean(
            _first(
                item,
                (
                    "url",
                    "link",
                    "document_url",
                    "patent_url",
                ),
            )
        )

        abstract = _clean(
            _first(
                item,
                (
                    "abstract",
                    "summary",
                    "description",
                ),
            )
        )

        snippet = _clean(
            _first(
                item,
                (
                    "snippet",
                    "text",
                    "highlight",
                    "matched_text",
                ),
            )
        )

        filing_date = _clean(
            _first(
                item,
                (
                    "filing_date",
                    "filingDate",
                    "date_filed",
                ),
            )
        )

        publication_date = _clean(
            _first(
                item,
                (
                    "publication_date",
                    "publicationDate",
                    "date_published",
                ),
            )
        )

        priority_date = _clean(
            _first(
                item,
                (
                    "priority_date",
                    "priorityDate",
                    "earliest_priority_date",
                ),
            )
        )

        applicants = _as_list(
            _first(
                item,
                (
                    "applicants",
                    "applicant",
                    "owners",
                ),
            )
        )

        inventors = _as_list(
            _first(
                item,
                (
                    "inventors",
                    "inventor",
                ),
            )
        )

        assignees = _as_list(
            _first(
                item,
                (
                    "assignees",
                    "assignee",
                    "owner",
                ),
            )
        )

        classifications = _as_list(
            _first(
                item,
                (
                    "classifications",
                    "classification",
                    "ipc",
                    "cpc",
                ),
            )
        )

        score = _safe_float(
            _first(
                item,
                (
                    "relevance_score",
                    "score",
                    "similarity",
                ),
            ),
            default=0.0,
        )

        return ProviderSearchResult(
            provider=self.provider_name,
            title=title,
            patent_number=patent_number,
            publication_number=publication_number,
            application_number=application_number,
            url=url,
            abstract=abstract,
            snippet=snippet,
            filing_date=filing_date,
            publication_date=publication_date,
            priority_date=priority_date,
            applicants=applicants,
            inventors=inventors,
            assignees=assignees,
            classifications=classifications,
            raw=dict(item),
            relevance_score=score,
            retrieval_status="retrieved",
        )

    def health_check(self) -> Dict[str, Any]:
        configured = bool(self.config.endpoint)

        return {
            "provider": self.provider_name,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "configured": configured,
            "available": self.enabled and configured,
            "status": (
                "configured"
                if self.enabled and configured
                else "not_configured"
            ),
        }


# ---------------------------------------------------------------------------
# Local JSON provider
# ---------------------------------------------------------------------------


class LocalJSONProvider(PatentSearchProvider):
    """
    Local/offline provider.

    Useful for:
        - testing
        - demonstrations
        - unit tests
        - locally exported patent datasets

    endpoint may point to a JSON file.

    Example JSON:

        [
            {
                "title": "...",
                "publication_number": "...",
                "abstract": "..."
            }
        ]
    """

    provider_name = PROVIDER_LOCAL_JSON
    display_name = "Local JSON Dataset"

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        **kwargs: Any,
    ) -> ProviderSearchResponse:
        start = time.perf_counter()

        path = self.config.endpoint

        if not path:
            return self._response_error(
                query,
                ValueError(
                    "No local JSON dataset configured."
                ),
                time.perf_counter() - start,
            )

        try:
            with open(
                path,
                "r",
                encoding="utf-8",
            ) as handle:
                payload = json.load(handle)

            if isinstance(payload, dict):
                records = (
                    payload.get("results")
                    or payload.get("items")
                    or payload.get("documents")
                    or payload.get("data")
                    or []
                )
            else:
                records = payload

            if not isinstance(records, list):
                records = []

            query_tokens = {
                token.lower()
                for token in query.split()
                if len(token) >= 3
            }

            results: List[ProviderSearchResult] = []

            for item in records:
                if not isinstance(item, Mapping):
                    continue

                text = " ".join(
                    [
                        _clean(item.get("title")),
                        _clean(item.get("abstract")),
                        _clean(item.get("claims")),
                        _clean(item.get("description")),
                    ]
                ).lower()

                matched = sum(
                    1
                    for token in query_tokens
                    if token in text
                )

                if query_tokens:
                    score = matched / len(query_tokens)
                else:
                    score = 0.0

                normalized = GenericJSONAPIProvider(
                    config=ProviderConfig(
                        name=PROVIDER_GENERIC_JSON,
                        display_name="Normalizer",
                    )
                )._normalize_result(item)

                normalized.provider = self.provider_name
                normalized.relevance_score = score

                if score > 0 or not query_tokens:
                    results.append(normalized)

            results.sort(
                key=lambda item: item.relevance_score,
                reverse=True,
            )

            results = results[:max_results]

            return ProviderSearchResponse(
                provider=self.provider_name,
                query=query,
                results=results,
                success=True,
                elapsed_seconds=time.perf_counter() - start,
                metadata={
                    "mode": "local_json",
                    "dataset": path,
                    "returned_results": len(results),
                },
            )

        except Exception as exc:
            return self._response_error(
                query,
                exc,
                time.perf_counter() - start,
            )

    def health_check(self) -> Dict[str, Any]:
        path = self.config.endpoint

        exists = bool(
            path
            and os.path.isfile(path)
        )

        return {
            "provider": self.provider_name,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "configured": bool(path),
            "available": self.enabled and exists,
            "status": (
                "ready"
                if self.enabled and exists
                else "dataset_missing"
            ),
        }


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------


class PatentSearchProviderRegistry:
    """
    Central registry for all search providers.

    The search engine should depend on this registry rather than knowing
    provider-specific implementation details.
    """

    def __init__(
        self,
        providers: Optional[Iterable[PatentSearchProvider]] = None,
    ) -> None:
        self._providers: Dict[str, PatentSearchProvider] = {}

        if providers:
            for provider in providers:
                self.register(provider)

    def register(
        self,
        provider: PatentSearchProvider,
        overwrite: bool = True,
    ) -> None:
        if not isinstance(provider, PatentSearchProvider):
            raise TypeError(
                "provider must inherit from PatentSearchProvider"
            )

        name = provider.provider_name

        if name in self._providers and not overwrite:
            raise ValueError(
                f"Provider already registered: {name}"
            )

        self._providers[name] = provider

    def unregister(
        self,
        provider_name: str,
    ) -> None:
        self._providers.pop(provider_name, None)

    def get(
        self,
        provider_name: str,
    ) -> PatentSearchProvider:
        if provider_name not in self._providers:
            raise KeyError(
                f"Unknown patent search provider: {provider_name}"
            )

        return self._providers[provider_name]

    def has(
        self,
        provider_name: str,
    ) -> bool:
        return provider_name in self._providers

    def names(self) -> List[str]:
        return sorted(self._providers.keys())

    def providers(self) -> List[PatentSearchProvider]:
        return list(self._providers.values())

    def available(self) -> List[str]:
        return [
            provider.provider_name
            for provider in self._providers.values()
            if provider.health_check().get("available")
        ]

    def search(
        self,
        provider_name: str,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        **kwargs: Any,
    ) -> ProviderSearchResponse:
        provider = self.get(provider_name)

        if not provider.enabled:
            return ProviderSearchResponse(
                provider=provider_name,
                query=query,
                results=[],
                success=False,
                error="Provider is disabled.",
            )

        return provider.search(
            query=query,
            max_results=max_results,
            **kwargs,
        )

    def health_check(self) -> Dict[str, Dict[str, Any]]:
        return {
            provider.provider_name: provider.health_check()
            for provider in self._providers.values()
        }

    def search_all(
        self,
        query: str,
        provider_names: Optional[Sequence[str]] = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> Dict[str, ProviderSearchResponse]:
        names = (
            list(provider_names)
            if provider_names
            else self.names()
        )

        output: Dict[str, ProviderSearchResponse] = {}

        for name in names:
            if not self.has(name):
                continue

            output[name] = self.search(
                provider_name=name,
                query=query,
                max_results=max_results,
            )

        return output


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def create_default_providers(
    generic_api_endpoint: Optional[str] = None,
    generic_api_key_env: Optional[str] = None,
    local_json_path: Optional[str] = None,
) -> List[PatentSearchProvider]:
    """
    Create the standard provider set.

    Public providers are configured as search-link providers.

    Generic API is only enabled when an endpoint is supplied.

    Local JSON is only enabled when a dataset path is supplied.
    """

    providers: List[PatentSearchProvider] = [
        GooglePatentsProvider(
            ProviderConfig(
                name=PROVIDER_GOOGLE_PATENTS,
                display_name="Google Patents",
            )
        ),
        EspacenetProvider(
            ProviderConfig(
                name=PROVIDER_ESPACENET,
                display_name="Espacenet",
            )
        ),
        WIPOPatentscopeProvider(
            ProviderConfig(
                name=PROVIDER_WIPO,
                display_name="WIPO PATENTSCOPE",
            )
        ),
    ]

    if generic_api_endpoint:
        providers.append(
            GenericJSONAPIProvider(
                ProviderConfig(
                    name=PROVIDER_GENERIC_JSON,
                    display_name="Generic JSON Patent API",
                    endpoint=generic_api_endpoint,
                    api_key_env=generic_api_key_env,
                )
            )
        )

    if local_json_path:
        providers.append(
            LocalJSONProvider(
                ProviderConfig(
                    name=PROVIDER_LOCAL_JSON,
                    display_name="Local JSON Dataset",
                    endpoint=local_json_path,
                )
            )
        )

    return providers


def build_provider_registry(
    generic_api_endpoint: Optional[str] = None,
    generic_api_key_env: Optional[str] = None,
    local_json_path: Optional[str] = None,
) -> PatentSearchProviderRegistry:
    return PatentSearchProviderRegistry(
        create_default_providers(
            generic_api_endpoint=generic_api_endpoint,
            generic_api_key_env=generic_api_key_env,
            local_json_path=local_json_path,
        )
    )


def create_search_provider_registry(
    **kwargs: Any,
) -> PatentSearchProviderRegistry:
    """
    Backward-compatible factory alias.
    """
    return build_provider_registry(**kwargs)


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------


def search_with_provider(
    query: str,
    provider: str = PROVIDER_GOOGLE_PATENTS,
    max_results: int = DEFAULT_MAX_RESULTS,
    registry: Optional[PatentSearchProviderRegistry] = None,
    **kwargs: Any,
) -> ProviderSearchResponse:
    """
    Execute a provider search.

    Example:

        response = search_with_provider(
            "lithium ion battery thermal management"
        )
    """

    registry = registry or build_provider_registry()

    return registry.search(
        provider_name=provider,
        query=query,
        max_results=max_results,
        **kwargs,
    )


def search_multiple_providers(
    query: str,
    providers: Optional[Sequence[str]] = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    registry: Optional[PatentSearchProviderRegistry] = None,
) -> Dict[str, ProviderSearchResponse]:
    registry = registry or build_provider_registry()

    return registry.search_all(
        query=query,
        provider_names=providers,
        max_results=max_results,
    )


def provider_health_report(
    registry: Optional[PatentSearchProviderRegistry] = None,
) -> Dict[str, Dict[str, Any]]:
    registry = registry or build_provider_registry()
    return registry.health_check()


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def provider_result_to_search_engine_result(
    result: ProviderSearchResult,
) -> Dict[str, Any]:
    """
    Convert provider-neutral result into a dictionary compatible with the
    existing search-engine normalization layer.
    """

    return {
        "provider": result.provider,
        "title": result.title,
        "patent_number": (
            result.patent_number
            or result.publication_number
        ),
        "publication_number": result.publication_number,
        "application_number": result.application_number,
        "url": result.url,
        "abstract": result.abstract,
        "snippet": result.snippet,
        "filing_date": result.filing_date,
        "publication_date": result.publication_date,
        "priority_date": result.priority_date,
        "applicants": result.applicants,
        "inventors": result.inventors,
        "assignees": result.assignees,
        "classifications": result.classifications,
        "relevance_score": result.relevance_score,
        "retrieval_status": result.retrieval_status,
        "raw": result.raw,
    }


def provider_response_to_search_results(
    response: ProviderSearchResponse,
) -> List[Dict[str, Any]]:
    return [
        provider_result_to_search_engine_result(result)
        for result in response.results
    ]


def flatten_provider_responses(
    responses: Mapping[str, ProviderSearchResponse],
) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []

    for response in responses.values():
        output.extend(
            provider_response_to_search_results(response)
        )

    return output


# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------


def provider_from_environment() -> PatentSearchProviderRegistry:
    """
    Build provider registry from environment variables.

    Supported variables:

        PATENT_SEARCH_API_URL
        PATENT_SEARCH_API_KEY_ENV
        PATENT_LOCAL_JSON_PATH

    Example:

        PATENT_SEARCH_API_URL=https://example.com/api/search
        PATENT_SEARCH_API_KEY_ENV=MY_PATENT_API_KEY

    The actual API key remains in MY_PATENT_API_KEY and is never stored
    in source code.
    """

    return build_provider_registry(
        generic_api_endpoint=os.getenv(
            "PATENT_SEARCH_API_URL"
        ),
        generic_api_key_env=os.getenv(
            "PATENT_SEARCH_API_KEY_ENV"
        ),
        local_json_path=os.getenv(
            "PATENT_LOCAL_JSON_PATH"
        ),
    )


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------


Provider = PatentSearchProvider
ProviderRegistry = PatentSearchProviderRegistry
GooglePatentsSearchProvider = GooglePatentsProvider
EspacenetSearchProvider = EspacenetProvider
WIPOSearchProvider = WIPOPatentscopeProvider
JSONAPIProvider = GenericJSONAPIProvider


def get_default_provider_registry() -> PatentSearchProviderRegistry:
    return build_provider_registry()


__all__ = [
    "SEARCH_PROVIDERS_VERSION",

    "PROVIDER_GOOGLE_PATENTS",
    "PROVIDER_ESPACENET",
    "PROVIDER_WIPO",
    "PROVIDER_GENERIC_JSON",
    "PROVIDER_LOCAL_JSON",

    "ProviderConfig",
    "ProviderSearchResult",
    "ProviderSearchResponse",

    "HTTPClient",

    "PatentSearchProvider",
    "GooglePatentsProvider",
    "EspacenetProvider",
    "WIPOPatentscopeProvider",
    "GenericJSONAPIProvider",
    "LocalJSONProvider",

    "PatentSearchProviderRegistry",

    "create_default_providers",
    "build_provider_registry",
    "create_search_provider_registry",
    "get_default_provider_registry",

    "search_with_provider",
    "search_multiple_providers",
    "provider_health_report",

    "provider_result_to_search_engine_result",
    "provider_response_to_search_results",
    "flatten_provider_responses",

    "provider_from_environment",

    "Provider",
    "ProviderRegistry",
    "GooglePatentsSearchProvider",
    "EspacenetSearchProvider",
    "WIPOSearchProvider",
    "JSONAPIProvider",
]
