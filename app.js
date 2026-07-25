const app = document.getElementById("app");


function decodePayload(encoded) {

    try {

        const json = atob(
            encoded
                .replace(/-/g, "+")
                .replace(/_/g, "/")
        );

        return JSON.parse(json);

    } catch (e) {

        return null;

    }

}


function render(data) {

    if (!data) {

        app.innerHTML = `
            <div class="card">
                <p>
                No Telepatch identity found.
                </p>

                <p>
                Use @telepatchbot and run /new
                </p>
            </div>
        `;

        return;
    }


    app.innerHTML = `

        <div class="card">

            <h2>
                ${data.author.name}
            </h2>

            <p>
                Telepatch identity created.
            </p>

            <p>
                Version:
                ${data.v}
            </p>

        </div>

    `;

}


const hash = window.location.hash.substring(1);

const payload = decodePayload(hash);

render(payload);
