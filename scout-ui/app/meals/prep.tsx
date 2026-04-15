import { ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, fonts, shared } from "../../lib/styles";

export default function MealsPlaceholder() {
  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <View style={shared.card}>
        <Text style={styles.text}>Coming soon — this tab is part of the redesign demo placeholder set.</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20 },
  text: { fontSize: 13, color: colors.muted, fontFamily: fonts.body },
});
