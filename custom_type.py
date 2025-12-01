import logging

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from typing import Union, List, Tuple, Annotated

from operator import add


# PlanExecute不需要校验
class PlanExecute(TypedDict):
    input: str
    plan: List[Union[str, List[str]]]
    past_achievement: List[Tuple]
    past_steps: Annotated[List[str], add]
    response: str
    index: int
    workspace: str
    

class Plan(BaseModel):
    steps: List[str] = Field(descriptions="将要执行的步骤，确保步骤按照先后顺序排序")


class Response(BaseModel):
    response: str


class Act(BaseModel):
    action: Union[Response, Plan] = Field(
        description="""
            将要执行的动作，可以是Response类型也可以是Plan类型。
            如果不需要再执行任何步骤就可以输出结果，就使用Response。
            如果需要执行更多步骤，就使用Plan。
        """
    )
