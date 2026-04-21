# LLM Learning Journey

Backend Engineer → AI Engineer transition. 19-day hands-on schedule.



## >>>>>>>>>>>>>>>>>>>>>> Day 1: LLM Fundamentals <<<<<<<<<<<<<<<<<<<<<<<

**What I built:** CLI chat app with conversation history and token tracking.

**Key concepts:**
- LLMs are stateless — "memory" is just resending the full message list
- Tokens = smallest unit of text LLM processes to understand and genrate response,  1 token ~ 3-5 char on average
    Prompt tokens grew per turn: 33 → 99 → 156 → 181 → 229 cause i gave the input + reponse appended list each time
- Temperature=0 for deterministic output, higher for creativity
- System/User/Assistant roles structure every API call

**Stack:** Python, OpenAI SDK, gpt-4o-mini