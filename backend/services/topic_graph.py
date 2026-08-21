"""Production composition for the Topic Graph Builder module."""

from services.topic_graph_builder import (
    LLMRelationshipGenerator,
    SupabaseTopicGraphStore,
    TopicGraphBuilder,
)


topic_graph_builder = TopicGraphBuilder(
    store=SupabaseTopicGraphStore(),
    generator=LLMRelationshipGenerator(),
    batch_concurrency=2,
)
