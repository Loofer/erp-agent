from agent.rag.runtime import build_hybrid_retriever


def test_rag_runtime_skips_placeholder_zilliz_configuration() -> None:
    class Token:
        def get_secret_value(self):
            return "xxx"

    class Settings:
        zilliz_uri = "xxx"
        zilliz_token = Token()

    assert build_hybrid_retriever(Settings()) is None
