from typing import TypedDict, List, Union, Tuple, Annotated
from pydantic import BaseModel, Field
from operator import add

class VuePlanExecute(TypedDict):
    input: str
    index: int
    steps: List[Tuple[str, str, str]]
    diff: List[Tuple[str, str]]

class VuePlan(BaseModel):
    steps: List[Tuple[str, str, str]] = Field(
        descriptions="""
        要执行的步骤，每个步骤包括：文件名、操作类型、操作目的
        操作类型包括：create、edit、delete、rename、move、copy
        操作目的：一段自然语言描述对文件操作的目的
        """
    )
