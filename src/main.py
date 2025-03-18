from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class Person(BaseModel):
    id: int
    name: str
    age: int


persons = {}


@app.post("/persons/", response_model=Person)
async def create_person(person: Person) -> Person:
    persons[person.id] = person
    return person


@app.get("/persons/{person_id}", response_model=Person)
async def get_person(person_id: int) -> Person:
    if person_id not in persons:
        raise HTTPException(status_code=404, detail="Person not found")
    return persons[person_id]
