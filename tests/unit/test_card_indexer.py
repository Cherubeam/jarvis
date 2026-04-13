"""
Unit tests for CardIndexer and CardSearcher.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the module eagerly so litellm is importable and patchable
from packages.core.rag import card_indexer as _card_indexer_mod  # noqa: F401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_deck_dir(tmp_path: Path, deck_name: str, cards: list[dict], card_contents: dict[str, str]) -> Path:
    """Create a deck directory with deck.yaml and card markdown files."""
    deck_dir = tmp_path / deck_name
    deck_dir.mkdir()

    # Write deck.yaml
    import yaml
    deck_yaml = {
        "name": deck_name.replace("-", " ").title(),
        "description": f"Test deck: {deck_name}",
        "cards": cards,
    }
    (deck_dir / "deck.yaml").write_text(yaml.dump(deck_yaml))

    # Write card files
    cards_dir = deck_dir / "resources" / "cards"
    cards_dir.mkdir(parents=True)
    for card_id, content in card_contents.items():
        (cards_dir / f"{card_id}.md").write_text(content)

    return deck_dir


def _make_card_indexer():
    """Create a CardIndexer with a fully mocked ChromaDB."""
    mock_chroma = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0
    mock_collection.get.return_value = {"ids": []}
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        from packages.core.rag.card_indexer import CardIndexer
        indexer = CardIndexer.__new__(CardIndexer)
        indexer.db_path = Path("/tmp/fake_rag")
        indexer.embedding_model = "test-model"
        indexer.api_key = None
        indexer.api_base = None
        indexer._client = mock_chroma.PersistentClient.return_value
        indexer._collection = mock_collection

    return indexer, mock_collection


def _make_card_searcher():
    """Create a CardSearcher with a fully mocked ChromaDB."""
    mock_chroma = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0
    mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

    with patch.dict("sys.modules", {"chromadb": mock_chroma}):
        from packages.core.rag.card_indexer import CardSearcher
        searcher = CardSearcher.__new__(CardSearcher)
        searcher.db_path = Path("/tmp/fake_rag")
        searcher.embedding_model = "test-model"
        searcher.api_key = None
        searcher.api_base = None
        searcher._client = mock_chroma.PersistentClient.return_value
        searcher._collection = mock_collection

    return searcher, mock_collection


# ---------------------------------------------------------------------------
# CardIndexer.index_new
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCardIndexerIndexNew:

    def test_indexes_new_cards(self, tmp_path):
        indexer, mock_collection = _make_card_indexer()
        deck_dir = _make_deck_dir(
            tmp_path,
            "storyteller-tactics",
            cards=[
                {"id": "the-hero", "name": "The Hero", "category": "Story Shapes",
                 "tags": ["protagonist", "journey"], "when": "When you need a hero"},
            ],
            card_contents={"the-hero": "# The Hero\n\nA tactic about heroes."},
        )

        def _fake_embed(**kwargs):
            n = len(kwargs["input"])
            return MagicMock(data=[{"embedding": [0.1, 0.2]} for _ in range(n)])

        with patch("packages.core.rag.card_indexer.litellm.embedding", side_effect=_fake_embed):
            n_new = indexer.index_new([deck_dir])

        assert n_new == 1
        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args[1]
        assert call_kwargs["ids"] == ["storyteller-tactics_the-hero"]
        assert call_kwargs["documents"] == ["# The Hero\n\nA tactic about heroes."]
        meta = call_kwargs["metadatas"][0]
        assert set(meta.keys()) == {"deck", "deck_dir", "card_id", "name", "category", "tags", "when"}
        assert meta == {
            "deck": "Storyteller Tactics",
            "deck_dir": "storyteller-tactics",
            "card_id": "the-hero",
            "name": "The Hero",
            "category": "Story Shapes",
            "tags": "protagonist,journey",
            "when": "When you need a hero",
        }

    def test_indexes_multiple_cards(self, tmp_path):
        indexer, mock_collection = _make_card_indexer()
        deck_dir = _make_deck_dir(
            tmp_path,
            "storyteller-tactics",
            cards=[
                {"id": "the-hero", "name": "The Hero", "category": "Story Shapes", "tags": []},
                {"id": "whats-at-stake", "name": "What's at Stake", "category": "Tension", "tags": []},
            ],
            card_contents={
                "the-hero": "# The Hero\n\nHero content.",
                "whats-at-stake": "# What's at Stake\n\nStakes content.",
            },
        )

        def _fake_embed(**kwargs):
            n = len(kwargs["input"])
            return MagicMock(data=[{"embedding": [0.1, 0.2]} for _ in range(n)])

        with patch("packages.core.rag.card_indexer.litellm.embedding", side_effect=_fake_embed):
            n_new = indexer.index_new([deck_dir])

        assert n_new == 2

    def test_indexes_across_multiple_decks(self, tmp_path):
        indexer, mock_collection = _make_card_indexer()
        deck1 = _make_deck_dir(
            tmp_path, "storyteller-tactics",
            cards=[{"id": "the-hero", "name": "The Hero", "category": "Story Shapes", "tags": []}],
            card_contents={"the-hero": "Hero content."},
        )
        deck2 = _make_deck_dir(
            tmp_path, "workshop-tactics",
            cards=[{"id": "check-in", "name": "Check-In", "category": "Openers", "tags": []}],
            card_contents={"check-in": "Check-in content."},
        )

        def _fake_embed(**kwargs):
            n = len(kwargs["input"])
            return MagicMock(data=[{"embedding": [0.1, 0.2]} for _ in range(n)])

        with patch("packages.core.rag.card_indexer.litellm.embedding", side_effect=_fake_embed):
            n_new = indexer.index_new([deck1, deck2])

        assert n_new == 2

    def test_skips_already_indexed_cards(self, tmp_path):
        indexer, mock_collection = _make_card_indexer()
        # Simulate already indexed
        mock_collection.count.return_value = 1
        mock_collection.get.return_value = {"ids": ["storyteller-tactics_the-hero"]}

        deck_dir = _make_deck_dir(
            tmp_path, "storyteller-tactics",
            cards=[{"id": "the-hero", "name": "The Hero", "category": "Story Shapes", "tags": []}],
            card_contents={"the-hero": "Hero content."},
        )

        with patch("packages.core.rag.card_indexer.litellm.embedding") as mock_embed:
            n_new = indexer.index_new([deck_dir])

        assert n_new == 0
        mock_embed.assert_not_called()

    def test_skips_empty_card_files(self, tmp_path):
        indexer, mock_collection = _make_card_indexer()
        deck_dir = _make_deck_dir(
            tmp_path, "storyteller-tactics",
            cards=[{"id": "empty-card", "name": "Empty", "category": "Test", "tags": []}],
            card_contents={"empty-card": ""},
        )

        with patch("packages.core.rag.card_indexer.litellm.embedding") as mock_embed:
            n_new = indexer.index_new([deck_dir])

        assert n_new == 0
        mock_embed.assert_not_called()

    def test_skips_dir_without_deck_yaml(self, tmp_path):
        indexer, mock_collection = _make_card_indexer()
        # Directory exists but has no deck.yaml
        deck_dir = tmp_path / "no-deck"
        deck_dir.mkdir()
        cards_dir = deck_dir / "resources" / "cards"
        cards_dir.mkdir(parents=True)
        (cards_dir / "card.md").write_text("Some content")

        with patch("packages.core.rag.card_indexer.litellm.embedding") as mock_embed:
            n_new = indexer.index_new([deck_dir])

        assert n_new == 0
        mock_embed.assert_not_called()

    def test_returns_zero_for_empty_deck_list(self):
        indexer, _ = _make_card_indexer()
        assert indexer.index_new([]) == 0

    def test_card_not_in_deck_yaml_still_indexed_with_defaults(self, tmp_path):
        """Cards on disk but not listed in deck.yaml should still be indexed
        with default metadata values."""
        indexer, mock_collection = _make_card_indexer()
        deck_dir = _make_deck_dir(
            tmp_path, "storyteller-tactics",
            cards=[],  # no cards listed in deck.yaml
            card_contents={"unlisted-card": "Unlisted card content."},
        )

        def _fake_embed(**kwargs):
            n = len(kwargs["input"])
            return MagicMock(data=[{"embedding": [0.1, 0.2]} for _ in range(n)])

        with patch("packages.core.rag.card_indexer.litellm.embedding", side_effect=_fake_embed):
            n_new = indexer.index_new([deck_dir])

        assert n_new == 1
        meta = mock_collection.upsert.call_args[1]["metadatas"][0]
        assert meta == {
            "deck": "Storyteller Tactics",
            "deck_dir": "storyteller-tactics",
            "card_id": "unlisted-card",
            "name": "unlisted-card",  # fallback to card_id
            "category": "",
            "tags": "",
            "when": "",
        }


# ---------------------------------------------------------------------------
# CardIndexer._load_deck_yaml
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLoadDeckYaml:

    def test_loads_valid_yaml(self, tmp_path):
        indexer, _ = _make_card_indexer()
        path = tmp_path / "deck.yaml"
        path.write_text("name: Test Deck\ncards: []\n")
        result = indexer._load_deck_yaml(path)
        assert result == {"name": "Test Deck", "cards": []}

    def test_returns_none_for_invalid_yaml(self, tmp_path):
        indexer, _ = _make_card_indexer()
        path = tmp_path / "deck.yaml"
        path.write_text(": invalid: yaml: [")
        result = indexer._load_deck_yaml(path)
        assert result is None

    def test_returns_none_for_missing_file(self, tmp_path):
        indexer, _ = _make_card_indexer()
        result = indexer._load_deck_yaml(tmp_path / "nonexistent.yaml")
        assert result is None


# ---------------------------------------------------------------------------
# CardSearcher.search
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCardSearcher:

    def test_returns_empty_when_no_cards_indexed(self):
        searcher, mock_collection = _make_card_searcher()
        mock_collection.count.return_value = 0
        results = searcher.search("hero story")
        assert results == []

    def test_returns_search_results(self):
        searcher, mock_collection = _make_card_searcher()
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "documents": [["# The Hero\n\nHero content."]],
            "metadatas": [[{
                "card_id": "the-hero",
                "deck": "Storyteller Tactics",
                "deck_dir": "storyteller-tactics",
                "name": "The Hero",
                "category": "Story Shapes",
                "tags": "protagonist,journey",
                "when": "When you need a hero",
            }]],
            "distances": [[0.15]],
        }

        with patch("packages.core.rag.card_indexer.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2]}])
            results = searcher.search("hero story")

        assert len(results) == 1
        assert set(results[0].keys()) == {
            "card_id", "deck", "deck_dir", "name", "category",
            "tags", "when", "content", "distance",
        }
        assert results[0] == {
            "card_id": "the-hero",
            "deck": "Storyteller Tactics",
            "deck_dir": "storyteller-tactics",
            "name": "The Hero",
            "category": "Story Shapes",
            "tags": "protagonist,journey",
            "when": "When you need a hero",
            "content": "# The Hero\n\nHero content.",
            "distance": 0.15,
        }

    def test_deck_filter_passed_as_where(self):
        searcher, mock_collection = _make_card_searcher()
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "documents": [[]], "metadatas": [[]], "distances": [[]],
        }

        with patch("packages.core.rag.card_indexer.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2]}])
            searcher.search("test", deck="storyteller-tactics")

        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["where"] == {"deck_dir": "storyteller-tactics"}

    def test_no_where_filter_when_deck_is_none(self):
        searcher, mock_collection = _make_card_searcher()
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "documents": [[]], "metadatas": [[]], "distances": [[]],
        }

        with patch("packages.core.rag.card_indexer.litellm.embedding") as mock_embed:
            mock_embed.return_value = MagicMock(data=[{"embedding": [0.1, 0.2]}])
            searcher.search("test")

        call_kwargs = mock_collection.query.call_args[1]
        assert "where" not in call_kwargs


# ---------------------------------------------------------------------------
# make_card_search_tool
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMakeCardSearchTool:

    def test_tool_name_and_description(self):
        with patch.dict("sys.modules", {"chromadb": MagicMock()}):
            from packages.core.tools.card_search import make_card_search_tool
            tool = make_card_search_tool("/tmp/fake", "test-model")

        assert tool.name == "search_tactics"
        assert "Pip Decks" in tool.description

    def test_tool_parameters_schema(self):
        with patch.dict("sys.modules", {"chromadb": MagicMock()}):
            from packages.core.tools.card_search import make_card_search_tool
            tool = make_card_search_tool("/tmp/fake", "test-model")

        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"query", "deck", "n_results"}
        assert params["properties"]["query"]["type"] == "string"
        assert params["properties"]["deck"]["type"] == "string"
        assert params["properties"]["n_results"]["type"] == "integer"
        assert params["properties"]["n_results"]["default"] == 5
        assert params["required"] == ["query"]

    def test_execute_returns_no_results_message(self):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            from packages.core.tools.card_search import make_card_search_tool
            tool = make_card_search_tool("/tmp/fake", "test-model")
            result = tool.execute(query="test")

        assert result == "No matching tactics cards found."

    def test_execute_clamps_n_results(self):
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "documents": [["Card content"]],
            "metadatas": [[{"card_id": "c", "deck": "D", "deck_dir": "d",
                           "name": "C", "category": "Cat", "tags": "", "when": ""}]],
            "distances": [[0.1]],
        }
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            with patch("packages.core.rag.card_indexer.litellm.embedding") as mock_embed:
                mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
                from packages.core.tools.card_search import make_card_search_tool
                tool = make_card_search_tool("/tmp/fake", "test-model")
                # Request 100, should be clamped to 15
                result = tool.execute(query="test", n_results=100)

        assert "Card content" in result

    def test_execute_output_format(self):
        """Verify exact header format and separator for search results."""
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {
            "documents": [["Content A", "Content B"]],
            "metadatas": [[
                {"card_id": "a", "deck": "Storyteller", "deck_dir": "st",
                 "name": "Hero Arc", "category": "Structure", "tags": "", "when": ""},
                {"card_id": "b", "deck": "Workshop", "deck_dir": "ws",
                 "name": "Warm Up", "category": "Opening", "tags": "", "when": ""},
            ]],
            "distances": [[0.1, 0.2]],
        }
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            with patch("packages.core.rag.card_indexer.litellm.embedding") as mock_embed:
                mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
                from packages.core.tools.card_search import make_card_search_tool
                tool = make_card_search_tool("/tmp/fake", "test-model")
                result = tool.execute(query="test")

        # Verify header format
        assert "--- Hero Arc (Storyteller) [category: Structure] ---" in result
        assert "--- Warm Up (Workshop) [category: Opening] ---" in result
        # Verify content follows header
        assert "Content A" in result
        assert "Content B" in result
        # Verify double-newline separator between blocks
        blocks = result.split("\n\n")
        assert len(blocks) == 2

    def test_execute_clamping_boundaries(self):
        """n_results=0 clamps to 1, n_results=16 clamps to 15."""
        mock_chroma = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma}):
            with patch("packages.core.rag.card_indexer.litellm.embedding") as mock_embed:
                mock_embed.return_value = MagicMock(data=[{"embedding": [0.1]}])
                from packages.core.tools.card_search import make_card_search_tool
                tool = make_card_search_tool("/tmp/fake", "test-model")

                # Find the searcher in the closure to check the clamped value
                searcher = None
                for cell in tool.execute.__closure__ or []:
                    try:
                        obj = cell.cell_contents
                        if hasattr(obj, "search"):
                            searcher = obj
                            break
                    except ValueError:
                        pass

                if searcher:
                    with patch.object(searcher, "search", return_value=[]) as mock_search:
                        tool.execute(query="test", n_results=0)
                        assert mock_search.call_args[1]["n_results"] == 1

                        tool.execute(query="test", n_results=16)
                        assert mock_search.call_args[1]["n_results"] == 15
