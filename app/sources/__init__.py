from app.sources.adapters import OwnedDemandAdapter, AuthorizedPublicSourceAdapter, SearchIntentAdapter

owned_adapter = OwnedDemandAdapter()
public_adapter = AuthorizedPublicSourceAdapter()
search_adapter = SearchIntentAdapter()

__all__ = ["owned_adapter", "public_adapter", "search_adapter", "OwnedDemandAdapter", "AuthorizedPublicSourceAdapter", "SearchIntentAdapter"]
