package main

import (
	"os"
	"go.yaml.in/yaml/v4"
	"go.yaml.in/yaml/v4/plugin/aliasdata"
	"go.yaml.in/yaml/v4/plugin/functiontag"
)

func main() {
	aliasPlugin, _ := aliasdata.New(aliasdata.WithPath(true))
	functionPlugin, _ := functiontag.New(
		nil, map[string]any{"aliases": "alias-data"})
	options := []yaml.Option{
		yaml.WithPlugin(aliasPlugin),
		yaml.WithPlugin(functionPlugin)}
	input, _ := os.ReadFile("input.yaml")
	var value any
	yaml.Load(input, &value, options...)
	output, _ := yaml.Dump(value, options...)
	os.Stdout.Write(output)
}
