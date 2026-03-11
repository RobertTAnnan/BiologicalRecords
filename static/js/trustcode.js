document.addEventListener("DOMContentLoaded", () => {

    let inputs = document.querySelectorAll(".code-input input");
    let form = document.querySelector("form");
    let hiddenInput = document.getElementById("trust_code");

    function getTrustCode() {
        return Array.from(inputs)
            .map(input => input.value.toUpperCase())
            .join("");
    }

    inputs.forEach((input, index) => {

        input.addEventListener("input", (e) => {

            let value = e.target.value;

            // Only allow one character
            if (value.length > 1) {
                value = value[0];
                input.value = value;
            }

            // Move forward
            if (value && index < inputs.length - 1) {
                inputs[index + 1].focus();
            }

        });

        input.addEventListener("keydown", (e) => {

            // Move backwards with backspace
            if (e.key === "Backspace" && input.value === "" && index > 0) {
                inputs[index - 1].focus();
            }

        });

    });

    // Handle pasting full code
    let container = document.querySelector(".code-input");

    container.addEventListener("paste", (e) => {

        let pasteData = e.clipboardData.getData("text").trim();
        let chars = pasteData.slice(0, inputs.length).split("");

        chars.forEach((char, i) => {
            inputs[i].value = char;
        });

        e.preventDefault();

    });

    // Merge inputs before form submit
    form.addEventListener("submit", () => {
        hiddenInput.value = getTrustCode();
    });

});

/** Commented out for testing
document.querySelector("form").addEventListener("submit", (e) => {
    e.preventDefault(); // stop submit for testing
    console.log("Trust Code:", document.getElementById("trust_code").value);
});
**/