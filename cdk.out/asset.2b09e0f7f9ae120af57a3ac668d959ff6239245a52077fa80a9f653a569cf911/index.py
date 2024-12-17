import json
import boto3
import os
import re
from openai import AzureOpenAI
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities import parameters
import anthropic
from openai import OpenAI

logger = Logger(level="INFO")

# Loading the API KEYs for the LLM and related services
try:
    ANTHROPIC_API_KEY = json.loads(parameters.get_secret("/ai-agent/ANTHROPIC_API_KEY"))["/ai-agent/ANTHROPIC_API_KEY"]
except ValueError:
    ANTHROPIC_API_KEY = parameters.get_secret("/ai-agent/ANTHROPIC_API_KEY")
try:
    OPENAI_API_KEY = json.loads(parameters.get_secret("/ai-agent/OPENAI_API_KEY"))["/ai-agent/OPENAI_API_KEY"]
except ValueError:
    OPENAI_API_KEY = parameters.get_secret("/ai-agent/OPENAI_API_KEY")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

from anthropic.types import Message, TextBlock, ToolUseBlock

def convert_claude_message_to_json(message):
    message_dict = {
        "message" : {
            "role": message.role,
            "content": [],
        }, 
        "metadata" : {
            "stop_reason": message.stop_reason,
            "stop_sequence": message.stop_sequence,
            "type": message.type,
            "usage": {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens
            }
        }
    }
    
    for block in message.content:
        if isinstance(block, TextBlock):
            message_dict["message"]["content"].append({
                "text": block.text,
                "type": block.type
            })
        elif isinstance(block, ToolUseBlock):
            message_dict["message"]["content"].append({
                "id": block.id,
                "input": block.input,
                "name": block.name,
                "type": block.type
            })
    
    return message_dict

def convert_gpt4_message_to_json(message):
    # TODO Add implementation for GPT-4
    message_dict = {
        "message" : {
        }, 
        "metadata" : {
        }
    }
    return message_dict

def lambda_handler(event, context):
    # Get system, messages, and model from event
    system = event.get('system')
    messages = event.get('messages')
    tools = event.get('tools', [])
    model = event.get('model', 'claude-3.5').lower()  # Default to Claude 3
    
    try:
        if 'claude' in model:
            #Send a request to Claude
            response = anthropic_client.messages.create(
                system = system,
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                tools=tools,
                messages=messages
            )

            assistant_message = convert_claude_message_to_json(response)

            # Update messages to include Claude's response
            messages.append(assistant_message["message"])
            
            logger.info(f"Claude result: {response.content[0].text}")
            
        elif 'gpt-4' in model:

 
            completion = openai_client.chat.completions.create(
                model="gpt-4",
                tools=tools,
                messages=messages
            )            
            # Update messages to include GPT-4's response
            assistant_message = convert_gpt4_message_to_json(completion.choices[0])

            messages.append(assistant_message["message"])
            
            logger.info(f"GPT-4 result: {completion.choices[0].message.content}")
            
        else:
            raise ValueError(f"Unsupported model: {model}")
            
        return {
            'statusCode': 200,
            'body': {
                'messages': messages,
                'metadata' : assistant_message["metadata"]
            }
        }
        
    except Exception as e:
        logger.error(e)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


if __name__ == "__main__":
    # Test event for Claude 3
    test_event_claude = {
        'model': 'claude-3',
        'system': "You are chatbot, who is helping people with answers to their questions.",
        'messages': [
            {
                "role": "user", 
                "content": "What is 2+2?"
            }
        ],
        'tools': [
            {
                "name": "get_db_schema",
                "description": "Describe the schema of the SQLite database, including table names, and column names and types.",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    }
    
    # Call lambda handler with test events
    print("\nTesting Claude 3:")
    response_claude = lambda_handler(test_event_claude, None)
    print(response_claude)

    # Test event for GPT-4
    test_event_gpt4 = {
        'model': 'gpt-4',
        'messages': [
            {"role": "user", "content": "What is 2+2?"}
        ],
        'tools': [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"}
                        },
                    },
                },
            }
        ]
    }
    
    
    print("\nTesting GPT-4:")
    response_gpt4 = lambda_handler(test_event_gpt4, None)
    print(response_gpt4)
