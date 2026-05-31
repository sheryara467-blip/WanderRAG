# WanderRAG

WanderRAG is an AI-powered Pakistan tourism assistant and booking platform built for a Final Year Project. It uses RAG (Retrieval-Augmented Generation) to give accurate tourism answers based on real data.

## Features

* AI-powered tourism chatbot for natural language queries
* Semantic similarity search using Pinecone vector database
* Grounded responses generated with Groq LLM and RAG pipeline
* Conversational booking assistant with multi-step booking flow
* Admin dashboard for managing tourism places and bookings
* CSV import/export support for bulk data management
* Smart incremental sync system that only re-embeds updated records

## Tech Stack

* FastAPI for backend APIs
* SQLite as the main relational database
* Pinecone for vector storage and semantic search
* Sentence Transformers for local embeddings generation
* Groq API for LLM-based conversational responses
* HTML, CSS, and Vanilla JavaScript for frontend UI

## Project Structure

* `backend/` → FastAPI server, database, routes, services
* `frontend/` → tourist UI and admin dashboard
* `backend/data/` → SQLite database and seed data

## Setup

1. Create and activate virtual environment
2. Install dependencies
3. Add your API keys in `.env`
4. Run the server

## Running Commands

### Windows

```bash
cd Tourism_assistant\backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### macOS / Linux

```bash
cd Tourism_assistant/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Open in Browser

* Tourist UI: `http://127.0.0.1:8000/`
* Admin Dashboard: `http://127.0.0.1:8000/admin`
* API Docs: `http://127.0.0.1:8000/docs`

## Important Note

After starting the server for the first time, open the admin dashboard and run the sync process to upload tourism embeddings into Pinecone. This enables semantic search and AI-powered retrieval.

## Main API Endpoints

* `GET /api/health`
* `POST /api/chat`
* `GET /api/places`
* `POST /api/sync`
* `POST /api/booking-agent/message`

## Key Components

### SQLite

Stores:

* tourism places
* packages
* bookings

Acts as:

> Main source of truth

### Pinecone

Stores:

* vector embeddings

Acts as:

> semantic similarity search engine

### Groq LLM

Used for:

* conversational answers
* booking extraction
* natural language generation

## Core Innovation

### Incremental Sync Engine

Instead of re-embedding the entire dataset:

* only changed records are re-embedded
* improves performance
* reduces compute cost

## Developed For

Final Year Project (FYP)

**Project Title:** WanderRAG — AI Powered Pakistan Tourism Guide & Booking Assistant

## License

This project is developed for educational and learning purposes.
