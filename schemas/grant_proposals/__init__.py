
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String

Base = declarative_base()

class GrantProposals(Base):
    __tablename__ = "grant_proposals"

    id = Column(Integer, primary_key=True)
    mention = Column(String)
    amount = Column(Integer)
    description = Column(String)
    timer = Column(Integer)
    channel_id = Column(Integer)

    def __repr__(self) -> str:
        return f"""
        <GrantProposal(id={self.id}, mention={self.mention}, amount={self.mention},
        deescription={self.description}, timer={self.timer}, channel_id={self.channel_id}"""


  
