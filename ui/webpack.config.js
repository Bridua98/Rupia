const fs = require("fs");
const path = require("path");
const webpack = require("webpack");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");

module.exports = (_env, argv) => {
  const entryDir = path.resolve(__dirname, "js/entrypoints");
  const entry = {
    main: path.resolve(__dirname, "js/index.js"),
  };
  if (fs.existsSync(entryDir)) {
    for (const file of fs.readdirSync(entryDir)) {
      if (file.endsWith(".js")) {
        entry[path.basename(file, ".js")] = path.join(entryDir, file);
      }
    }
  }

  return {
    mode: argv.mode || "development",
    entry,
    output: {
      path: path.resolve(__dirname, "../static/webpack_bundles"),
      filename: "[name].js",
      publicPath: "/static/webpack_bundles/",
      clean: true,
    },
    devtool: argv.mode === "production" ? false : "source-map",
    module: {
      rules: [
        {
          test: /\.jsx?$/,
          exclude: /node_modules/,
          use: "babel-loader",
        },
        {
          test: /\.scss$/,
          use: [
            MiniCssExtractPlugin.loader,
            "css-loader",
            {
              loader: "sass-loader",
              options: {
                sassOptions: {
                  quietDeps: true,
                  silenceDeprecations: ["import"],
                },
              },
            },
          ],
        },
        {
          test: /\.css$/,
          use: [MiniCssExtractPlugin.loader, "css-loader"],
        },
      ],
    },
    resolve: {
      extensions: [".js", ".jsx"],
    },
    plugins: [
      new MiniCssExtractPlugin({ filename: "styles.css" }),
      new webpack.ProvidePlugin({
        $: "jquery",
        jQuery: "jquery",
      }),
    ],
  };
};
