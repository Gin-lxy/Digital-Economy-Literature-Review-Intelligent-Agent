# Dify Deployment Guide

This guide maps the local RAG prototype to a Dify-based deployable web app.

## 1. Prerequisites

- A running Dify instance (cloud or self-hosted).
- Available LLM provider credentials in Dify.
- Your paper corpus ready for knowledge import.

## 2. Create Knowledge Base

1. In Dify, create a new Knowledge Base (KB), e.g. `digital-economy-kb`.
2. Upload all cleaned PDFs (or chunked text files).
3. Configure indexing:
   - chunk size: near 800 chars
   - overlap: near 120 chars
4. Wait until indexing completes.

## 3. Build Application

1. Create a new Chat App in Dify.
2. Attach the KB created above.
3. Set retrieval mode to semantic search (top-k around 6).
4. Add a system prompt equivalent to local prompt rules:
   - academic style
   - synthesize instead of copying
   - mandatory citations `[source:page]`

## 4. Test and Tune

1. Use sample topics from your thesis scope.
2. Check if citations are visible and correctly linked.
3. Adjust:
   - top-k
   - temperature
   - prompt wording
   - reranker (if enabled)

## 5. Publish

1. Publish internal/external app link.
2. Save screenshots:
   - app config
   - chat generation results
   - citation evidence
3. Include link and screenshots in thesis appendix.

## 6. Deliverable Checklist

- Dify app URL
- Prompt configuration screenshot
- Knowledge base indexing screenshot
- At least 3 generated examples with citations
