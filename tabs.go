package main
import (
	"encoding/json"
	"os"
	"go.yaml.in/yaml/v4"
	"go.yaml.in/yaml/v4/plugin/tabindent"
)
func main() {
	input, _ := os.ReadFile("tabs.yaml")
	var value any
	if err := yaml.Load(input, &value,
		yaml.WithPlugin(tabindent.New())); err != nil {
		panic(err)
	}
	output := json.NewEncoder(os.Stdout)
	output.SetIndent("", "  ")
	if err := output.Encode(value); err != nil { panic(err) }
}
