import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

gpt_client = OpenAI()


OPENAI_GPT_MODEL="gpt-4.1-mini-2025-04-14"
OPENAI_GPT_MODEL_LG="gpt-4.1-2025-04-14"
FAMILY_INFO_STR = os.environ.get('FAMILY_INFO_STR')

if not FAMILY_INFO_STR:
    print('====================')
    print('FAMILY_INFO_STR is not provided!')


MAIN_PROMPT = '''
**YOUR ROLE**
You are a friendly, conversational social robot that can chat with the family and answer questions.


The family info:
{FAMILY_INFO}


The latest USER input is: {COMMAND}.


{IMAGE_PROMPT}


In plain text, what is your response?
'''.strip() + '\n\n\n'






SYSTEM_PROMPT = '''
You are a helpful agent controlling a domestic social robot,
and your goal is to promote family-connection making.
The transcriptions you are provided with may be from various people within the family.
'''


def generate_response(all_messages, img_path=None):
    
    msg_sys = {
        'role': 'system',
        'content': SYSTEM_PROMPT
    }
    
    if img_path is None:
        prompt = MAIN_PROMPT.format(
            FAMILY_INFO=FAMILY_INFO_STR,
            COMMAND=all_messages[-1]['content'],
            IMAGE_PROMPT=''
        )
        msg_last = {
            'role': 'user',
            'content': prompt
        }
    else:
        prompt = MAIN_PROMPT.format(
            FAMILY_INFO=FAMILY_INFO_STR,
            COMMAND=all_messages[-1]['content'],
            IMAGE_PROMPT='You are also provided with the picture of the view in front of you.'
        )
        msg_last = {
            'role': 'user',
            'content': prompt
        }
        # TODO
        msg_last = {
            'role': 'user',
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type":"file",
                    "file":{
                        "file_data":"data:application/pdf;base64,JVBERi0xLjUNJeLjz9MN...",
                        "filename":"competion-sidebar.pdf"
                    }
                }
            ],
        }

    messages = [msg_sys] + all_messages[:-1] + [msg_last]
    res = ''
    try:
        ans = gpt_client.chat.completions.create(
            model=OPENAI_GPT_MODEL,
            max_completion_tokens=256,
            stop="\n\n\n",
            messages=messages,
            temperature=0.2,
            top_p=1,
            n=1,
        )

        res = ans.choices[0].message.content
        token_output = ans.usage.completion_tokens
    except Exception as e:
        print(f'[ERROR][generate_response]: {e}')
    return res

