To create a webpage for the event we gave this prompt to lovable

```
Write a simple webpage that retrieves the following event.json from [a url](https://0792-147-12-150-36.ngrok-free.app/api/event) and shows a nice, simple, polished event page

bypass the ngrok browser warning

This is what you have to do to bypass the browser warning: You have to include the request header ngrok-skip-browser-warning with any value in the request header.
The exact syntax of what is to be included depends on the type of the api call you're making.
For instance for a fetch request in javascript, this is what has to be included to bypass the warning:

fetch(url, {
      method: "get",
      headers: new Headers({
        "ngrok-skip-browser-warning": "69420",
      }),
    })
      .then((response) => response.json())
      .then((data) => console.log(data))
      .catch((err) => console.log(err));

--- event.json format below ---
<<paste content of event.json here>>
```