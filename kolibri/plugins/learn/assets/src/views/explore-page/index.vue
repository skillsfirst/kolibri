<template>

  <div>

    <page-header :title="title">
      <div slot="icon">
        <mat-svg v-if="isRoot" category="action" name="explore"/>
        <mat-svg v-else category="file" name="folder"/>
      </div>
    </page-header>

    <p class="page-description" v-if="topic.description">
      {{ topic.description }}
    </p>

    <ui-select
      :label="$tr('display')"
      :options="filterOptions"
      v-model="selectedFilter"
      class="filter"
    />

    <span class="visuallyhidden" v-if="subtopics.length">{{ $tr('navigate') }}</span>

    <card-grid v-if="contents.length">
      <content-grid-item
        v-for="content in contents"
        v-show="selectedFilter.value === 'all' || selectedFilter.value === content.kind"
        :key="content.id"
        class="card"
        :title="content.title"
        :thumbnail="content.thumbnail"
        :kind="content.kind"
        :progress="content.progress"
        :link="genLink(content)"/>
    </card-grid>

  </div>

</template>


<script>

  const getCurrentChannelObject = require('kolibri.coreVue.vuex.getters').getCurrentChannelObject;
  const PageNames = require('../../constants').PageNames;
  const ContentNodeKinds = require('kolibri.coreVue.vuex.constants').ContentNodeKinds;
  const some = require('lodash/some');
  const forEach = require('lodash/forEach');

  module.exports = {
    $trNameSpace: 'learnExplore',
    $trs: {
      explore: 'Topics',
      navigate: 'Navigate content using headings',
      all: 'All content',
      topics: 'Topics',
      exercises: 'Exercises',
      videos: 'Videos',
      audio: 'Audio',
      documents: 'Documents',
      html5: 'HTML5 Apps',
      display: 'Display',
    },
    components: {
      'page-header': require('../page-header'),
      'topic-list-item': require('../topic-list-item'),
      'content-grid-item': require('../content-grid-item'),
      'card-grid': require('../card-grid'),
      'card-list': require('../card-list'),
      'ui-select': require('keen-ui/src/UiSelect'),
    },
    data: () => ({
      selectedFilter: '',
    }),
    computed: {
      filterOptions() {
        const options = [{ label: this.$tr('all'), value: 'all' }];
        const kindLabelsMap = {
          [ContentNodeKinds.TOPIC]: this.$tr('topics'),
          [ContentNodeKinds.EXERCISE]: this.$tr('exercises'),
          [ContentNodeKinds.VIDEO]: this.$tr('videos'),
          [ContentNodeKinds.AUDIO]: this.$tr('audio'),
          [ContentNodeKinds.DOCUMENT]: this.$tr('documents'),
          [ContentNodeKinds.HTML5]: this.$tr('html5'),
        };
        forEach(kindLabelsMap, (value, key) => {
          if (this.contentsContain(key)) {
            options.push({ label: value, value: key });
          }
        });
        return options;
      },
      title() {
        return this.isRoot ? this.$tr('explore') : this.topic.title;
      },
      subtopics() {
        return this.contents.filter(content => content.kind === ContentNodeKinds.TOPIC);
      },
    },
    methods: {
      contentsContain(kind) {
        return some(this.contents, content => content.kind === kind);
      },
      genLink(node) {
        if (node.kind !== ContentNodeKinds.TOPIC) {
          return {
            name: PageNames.EXPLORE_CONTENT,
            params: { channel_id: this.channelId, id: node.id },
          };
        }
        return {
          name: PageNames.EXPLORE_TOPIC,
          params: { channel_id: this.channelId, id: node.id },
        };
      },
    },
    mounted() {
      this.selectedFilter = this.filterOptions[0];
    },
    vuex: {
      getters: {
        topic: state => state.pageState.topic,
        contents: state => state.pageState.contents,
        isRoot: (state) => state.pageState.topic.id === getCurrentChannelObject(state).root_id,
        channelId: (state) => getCurrentChannelObject(state).id,
      },
    },
  };

</script>


<style lang="stylus" scoped>

  .page-description
    margin-top: 1em
    margin-bottom: 1em
    line-height: 1.5em

  .filter
    width: 200px
    margin-top: 2em

</style>
