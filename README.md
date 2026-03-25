# redis-agent-memory-demo

This demo showcases Redis Agent Memory Server.

## Running the Demo via Docker Compose

Follow these steps to run the demo locally using Docker Compose.

### Prerequisites

You will need two API keys to run this demo:

1.  **OpenAI API Key**: Used for the LLM. You can get one at [platform.openai.com](https://platform.openai.com/).
2.  **Tavily API Key**: Used for web search capabilities. You can get one at [tavily.com](https://tavily.com/).

### Setup

1.  Create a file named `.env` in the root directory of this project.
2.  Add your API keys to the `.env` file as follows:

    ```env
    OPENAI_API_KEY=your_openai_key_here
    TAVILY_API_KEY=your_tavily_key_here
    ```

### Run

Start the demo by running:

```bash
docker compose up -d
```

Once the containers are running, you can access the demo in your browser at `http://localhost:8080`.
